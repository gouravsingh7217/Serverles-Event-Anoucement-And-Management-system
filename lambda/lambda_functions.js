// ============================================================
// EventPulse — PRODUCTION FIXED LAMBDA (UPDATED)
// Node.js 20.x
// ============================================================

const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const mysql = require('mysql2/promise');
const { SNSClient, PublishCommand } = require('@aws-sdk/client-sns');

// ============================================================
// DB POOL
// ============================================================

let pool = null;

function getPool() {
  if (!pool) {
    pool = mysql.createPool({
      host: process.env.DB_HOST,
      user: process.env.DB_USER,
      password: process.env.DB_PASSWORD,
      database: process.env.DB_NAME,
      port: parseInt(process.env.DB_PORT || '3306'),
      waitForConnections: true,
      connectionLimit: 10,
      queueLimit: 0,
      ssl: { rejectUnauthorized: false }
    });
  }
  return pool;
}

// ============================================================
// SNS
// ============================================================

const sns = new SNSClient({
  region: process.env.AWS_REGION || 'ap-south-1'
});

// ============================================================
// CORS
// ============================================================

const CORS = {
  'Content-Type': 'application/json',
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers':
    'Content-Type,Authorization,X-Requested-With,X-Amz-Date,X-Api-Key,X-Amz-Security-Token',
  'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
};

// ============================================================
// LOGGING HELPERS
// ============================================================

function logInfo(action, data = {}) {
  console.log(JSON.stringify({
    level: "INFO",
    action,
    ...data,
    timestamp: new Date().toISOString()
  }));
}

function logError(action, error, data = {}) {
  console.error(JSON.stringify({
    level: "ERROR",
    action,
    error: error?.message || String(error),
    stack: error?.stack || undefined,
    ...data,
    timestamp: new Date().toISOString()
  }));
}

function logWarn(action, data = {}) {
  console.warn(JSON.stringify({
    level: "WARN",
    action,
    ...data,
    timestamp: new Date().toISOString()
  }));
}

// ============================================================
// HELPERS
// ============================================================

function ok(body, status = 200) {
  return {
    statusCode: status,
    headers: CORS,
    body: JSON.stringify(body)
  };
}

function err(message, status = 400) {
  return {
    statusCode: status,
    headers: CORS,
    body: JSON.stringify({ success: false, message })
  };
}

function parseBody(event) {
  if (!event.body) return {};

  try {
    return JSON.parse(
      event.isBase64Encoded
        ? Buffer.from(event.body, 'base64').toString('utf8')
        : event.body
    );
  } catch {
    return {};
  }
}

// ============================================================
// MAIN HANDLER
// ============================================================

exports.handler = async (event) => {

  const method = event.httpMethod || event.requestContext?.http?.method || '';

  const rawPath =
    event.rawPath ||
    event.path ||
    event.requestContext?.http?.path ||
    '';

  // normalize stage (/prod or /dev)
  const path = rawPath.replace(/^\/(prod|dev)/, '');

  logInfo("REQUEST_RECEIVED", { method, rawPath, path });

  if (method === 'OPTIONS') {
    logInfo("PREFLIGHT_OPTIONS", { path });
    return { statusCode: 200, headers: CORS, body: '' };
  }

  try {

    if (method === 'POST' && path.endsWith('/auth/signup')) {
      return await signup(event);
    }

    if (method === 'POST' && path.endsWith('/auth/login')) {
      return await login(event);
    }

    if (method === 'GET' && path.endsWith('/events')) {
      return await getEvents(event);
    }

    if (method === 'POST' && path.endsWith('/events')) {
      return await createEvent(event);
    }

    if (method === 'PUT' && path.startsWith('/events/')) {
      return await updateEvent(event);
    }

    if (method === 'DELETE' && path.startsWith('/events/')) {
      return await deleteEvent(event);
    }

    if (method === 'POST' && path.endsWith('/announce')) {
      return await announceEvent(event);
    }

    logWarn("ROUTE_NOT_FOUND", { method, path });
    return err(`Route not found: ${method} ${path}`, 404);

  } catch (e) {
    logError("UNHANDLED_EXCEPTION", e, { method, path });
    return err(e.message || 'Internal server error', 500);
  }
};

// ============================================================
// AUTH HELPERS
// ============================================================

function getUser(event) {
  const auth = event.headers?.Authorization || event.headers?.authorization;
  if (!auth) throw new Error("UNAUTHORIZED");

  const token = auth.replace("Bearer ", "");
  return jwt.verify(token, process.env.JWT_SECRET || "fallback_secret");
}

function requireAdmin(user) {
  if (!user || user.role !== 'admin') throw new Error("FORBIDDEN");
}

// ============================================================
// SIGNUP
// ============================================================

async function signup(event) {

  logInfo("USER_REGISTER_STARTED");

  const { full_name, email, password } = parseBody(event);

  if (!full_name || !email || !password) {
    logWarn("USER_REGISTER_VALIDATION_FAILED", { reason: "Missing required fields" });
    return err("full_name, email, password required");
  }

  logInfo("USER_REGISTER_FIELDS_VALIDATED", { email });

  const db = getPool();

  let existing;
  try {
    [existing] = await db.execute(
      `SELECT id FROM users WHERE email = ?`,
      [email.toLowerCase()]
    );
    logInfo("USER_REGISTER_DB_LOOKUP", { email, found: existing.length > 0 });
  } catch (e) {
    logError("DB_CONNECTION_FAILED", e, { action: "USER_REGISTER_DB_LOOKUP", email });
    throw e;
  }

  if (existing.length) {
    logWarn("USER_REGISTER_DUPLICATE", { email });
    return err("User already exists", 409);
  }

  let hash;
  try {
    hash = await bcrypt.hash(password, 10);
    logInfo("USER_REGISTER_PASSWORD_HASHED", { email });
  } catch (e) {
    logError("USER_REGISTER_HASH_FAILED", e, { email });
    throw e;
  }

  try {
    await db.execute(
      `INSERT INTO users (full_name, email, password_hash, role)
       VALUES (?, ?, ?, 'user')`,
      [full_name, email.toLowerCase(), hash]
    );
    logInfo("USER_REGISTER_SUCCESS", { email });
  } catch (e) {
    logError("DB_INSERT_FAILED", e, { action: "USER_REGISTER", email });
    throw e;
  }

  return ok({
    success: true,
    message: "User created successfully"
  });
}

// ============================================================
// LOGIN
// ============================================================

async function login(event) {

  logInfo("USER_LOGIN_STARTED");

  const { email, password } = parseBody(event);

  if (!email || !password) {
    logWarn("USER_LOGIN_VALIDATION_FAILED", { reason: "Missing email or password" });
    return err("Email and password required");
  }

  logInfo("USER_LOGIN_FIELDS_VALIDATED", { email });

  const db = getPool();

  let rows;
  try {
    [rows] = await db.execute(
      `SELECT id, full_name, email, password_hash, role
       FROM users WHERE email = ?`,
      [email.toLowerCase()]
    );
    logInfo("USER_LOGIN_DB_LOOKUP", { email, found: rows.length > 0 });
  } catch (e) {
    logError("DB_CONNECTION_FAILED", e, { action: "USER_LOGIN_DB_LOOKUP", email });
    throw e;
  }

  if (!rows.length) {
    logWarn("USER_LOGIN_NOT_FOUND", { email });
    return err("Invalid credentials", 401);
  }

  const user = rows[0];

  let match;
  try {
    match = await bcrypt.compare(password, user.password_hash);
    logInfo("USER_LOGIN_PASSWORD_CHECK", { email, match });
  } catch (e) {
    logError("USER_LOGIN_BCRYPT_FAILED", e, { email });
    throw e;
  }

  if (!match) {
    logWarn("USER_LOGIN_INVALID_PASSWORD", { email });
    return err("Invalid credentials", 401);
  }

  let token;
  try {
    token = jwt.sign(
      { id: user.id, email: user.email, role: user.role },
      process.env.JWT_SECRET || "fallback_secret",
      { expiresIn: "8h" }
    );
    logInfo("USER_LOGIN_TOKEN_ISSUED", { email, userId: user.id, role: user.role });
  } catch (e) {
    logError("USER_LOGIN_JWT_FAILED", e, { email });
    throw e;
  }

  logInfo("USER_LOGIN_SUCCESS", { email, userId: user.id, role: user.role });

  return ok({ success: true, token, user });
}

// ============================================================
// ANNOUNCE
// ============================================================

async function announceEvent(event) {

  logInfo("ANNOUNCE_EVENT_STARTED");

  let user;
  try {
    user = getUser(event);
    requireAdmin(user);
    logInfo("ANNOUNCE_EVENT_AUTH_OK", { userId: user.id, role: user.role });
  } catch (e) {
    logWarn("ANNOUNCE_EVENT_AUTH_FAILED", { reason: e.message });
    return err(e.message, e.message === "UNAUTHORIZED" ? 401 : 403);
  }

  const body = parseBody(event);
  const db = getPool();

  let finalEventId =
    body.event_id ||
    body.eventId ||
    body.id;

  const { title, date, time, venue, desc, subject } = body;

  if (!title || !date || !venue) {
    logWarn("ANNOUNCE_EVENT_VALIDATION_FAILED", { reason: "Missing title, date, or venue" });
    return err("title, date, venue required");
  }

  logInfo("ANNOUNCE_EVENT_FIELDS_VALIDATED", { title, date, venue, finalEventId });

  if (finalEventId) {
    let rows;
    try {
      [rows] = await db.execute(
        `SELECT id FROM events WHERE id = ?`,
        [finalEventId]
      );
      logInfo("ANNOUNCE_EVENT_DB_LOOKUP_BY_ID", { finalEventId, found: rows.length > 0 });
    } catch (e) {
      logError("DB_CONNECTION_FAILED", e, { action: "ANNOUNCE_EVENT_DB_LOOKUP_BY_ID", finalEventId });
      throw e;
    }

    if (!rows.length) {
      logWarn("ANNOUNCE_EVENT_NOT_FOUND", { finalEventId });
      return err("Event not found (invalid id)", 404);
    }

    finalEventId = rows[0].id;
  }

  if (!finalEventId) {
    let rows;
    try {
      [rows] = await db.execute(
        `SELECT id FROM events 
         WHERE title = ? 
         ORDER BY id DESC LIMIT 1`,
        [title]
      );
      logInfo("ANNOUNCE_EVENT_DB_LOOKUP_BY_TITLE", { title, found: rows.length > 0 });
    } catch (e) {
      logError("DB_CONNECTION_FAILED", e, { action: "ANNOUNCE_EVENT_DB_LOOKUP_BY_TITLE", title });
      throw e;
    }

    if (!rows.length) {
      logWarn("ANNOUNCE_EVENT_NOT_FOUND_BY_TITLE", { title });
      return err("Event not found (title mismatch)", 404);
    }

    finalEventId = rows[0].id;
  }

  const message = `
🎉 EVENT ANNOUNCEMENT

📌 ${title}
📅 ${date} ${time || ''}
📍 ${venue}

${desc || ''}

— EventPulse
`;

  logInfo("ANNOUNCE_EVENT_SNS_SEND_STARTED", { finalEventId, subject: subject || title });

  if (!process.env.SNS_TOPIC_ARN) {
    logError("ANNOUNCE_EVENT_SNS_CONFIG_MISSING", new Error("SNS_TOPIC_ARN not set"));
    return err("SNS_TOPIC_ARN missing in env", 500);
  }

  let snsRes;
  try {
    snsRes = await sns.send(
      new PublishCommand({
        TopicArn: process.env.SNS_TOPIC_ARN,
        Subject: subject || title,
        Message: message
      })
    );
    logInfo("ANNOUNCE_EVENT_SNS_SUCCESS", {
      finalEventId,
      snsMessageId: snsRes.MessageId
    });
  } catch (snsError) {
    logError("SNS_PUBLISH_FAILED", snsError, { finalEventId });
    return err("Failed to send SNS announcement", 500);
  }

  try {
    await db.execute(
      `INSERT INTO announcements (event_id, subject, message_body, sent_by, sns_message_id)
       VALUES (?, ?, ?, ?, ?)`,
      [finalEventId, subject || title, message, user.id, snsRes.MessageId || null]
    );
    logInfo("ANNOUNCE_EVENT_DB_INSERT_OK", { finalEventId, sentBy: user.id });
  } catch (e) {
    logError("DB_INSERT_FAILED", e, { action: "ANNOUNCE_EVENT_INSERT_ANNOUNCEMENT", finalEventId });
    throw e;
  }

  try {
    await db.execute(
      `UPDATE events SET announced=1, announced_at=NOW() WHERE id=?`,
      [finalEventId]
    );
    logInfo("ANNOUNCE_EVENT_DB_UPDATE_OK", { finalEventId });
  } catch (e) {
    logError("DB_UPDATE_FAILED", e, { action: "ANNOUNCE_EVENT_UPDATE_STATUS", finalEventId });
    throw e;
  }

  logInfo("ANNOUNCE_EVENT_COMPLETED", { finalEventId, snsMessageId: snsRes.MessageId });

  return ok({
    success: true,
    message: "Announcement sent successfully",
    event_id: finalEventId
  });
}

// ============================================================
// STUBS
// ============================================================

async function getEvents() {
  logInfo("GET_EVENTS_CALLED");
  return ok({ message: "getEvents not implemented yet" });
}

async function createEvent() {
  logInfo("CREATE_EVENT_CALLED");
  return ok({ message: "createEvent not implemented yet" });
}

async function updateEvent() {
  logInfo("UPDATE_EVENT_CALLED");
  return ok({ message: "updateEvent not implemented yet" });
}

async function deleteEvent() {
  logInfo("DELETE_EVENT_CALLED");
  return ok({ message: "deleteEvent not implemented yet" });
}