# 🚀 Serverless Event Announcement & Management System

A scalable cloud-native event management platform built using **AWS Serverless Architecture**.
This project enables organizations and users to create, manage, announce, and monitor events efficiently with secure authentication, automated notifications, and AI-powered assistance.

---

# 📌 Features

## ✅ User Features

* User Registration & Login
* JWT-based Authentication
* Create & Manage Events
* Event Announcements
* Real-time Event Updates
* AI Chatbot Assistance
* Responsive Frontend UI
* Secure API Access

---

# 🏗️ Architecture Overview

This project follows a **Serverless Microservices Architecture** on AWS.

## 🔥 Tech Stack

### Frontend

* React.js
* Tailwind CSS
* Axios

### Backend

* Python Flask APIs
* AWS Lambda
* API Gateway

### Authentication

* JWT Authorizer
* Secure Token Validation

### Database

* DynamoDB

### AI Integration

* Hugging Face API
* Mistral 7B Model

### DevOps & Deployment

* Docker
* Nginx
* GitHub Actions (Optional)
* AWS CloudWatch
* EC2 Deployment

---

# ☁️ AWS Services Used

| Service       | Purpose                |
| ------------- | ---------------------- |
| API Gateway   | API Management         |
| AWS Lambda    | Serverless Compute     |
| DynamoDB      | NoSQL Database         |
| CloudWatch    | Monitoring & Logs      |
| IAM           | Security & Permissions |
| EC2           | Deployment Server      |
| S3 (Optional) | Static Assets          |

---

# 🔄 Project Flow Diagram

```text
                    ┌─────────────────┐
                    │     Client      │
                    │ React Frontend  │
                    └────────┬────────┘
                             │
                             ▼
                   ┌──────────────────┐
                   │   API Gateway    │
                   └────────┬─────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
 ┌──────────────┐  ┌────────────────┐  ┌────────────────┐
 │ JWT Authorizer│  │ Event Lambda   │  │ AI Lambda      │
 │ Authentication│  │ APIs           │  │ Hugging Face   │
 └──────┬───────┘  └────────┬───────┘  └────────┬───────┘
        │                    │                   │
        ▼                    ▼                   ▼
 ┌──────────────┐     ┌──────────────┐    ┌──────────────┐
 │ JWT Tokens   │     │ DynamoDB     │    │ Mistral 7B   │
 │ Validation   │     │ Event Data   │    │ AI Model API │
 └──────────────┘     └──────────────┘    └──────────────┘
```

---

# 📂 Project Structure

```bash
project-root/
│
├── frontend/               # React Frontend
├── lambda/                 # AWS Lambda Functions
├── jwt-authorizer/         # JWT Authentication Service
├── python_llm/             # AI Chatbot Service
├── database/               # Database Configurations
├── .gitignore
├── README.md
└── deploy_django_app.sh
```

---

# 🔐 Authentication Flow

1. User logs in
2. JWT token generated
3. Token sent with API requests
4. JWT Authorizer validates token
5. Authorized access granted

---

# 🤖 AI Chatbot Integration

The platform integrates:

* Hugging Face Inference API
* Mistral-7B-Instruct-v0.3

Features:

* Event Assistance
* Query Resolution
* Smart Responses
* AI-powered Helpdesk

---

# 🐳 Docker Deployment

## Build Docker Image

```bash
docker build -t notes-app .
```

## Run Container

```bash
docker run -d -p 8000:8000 notes-app
```

## Check Running Containers

```bash
docker ps
```

---

# ⚙️ Environment Variables

Create a `.env` file:

```env
HF_TOKEN=your_huggingface_token
JWT_SECRET=your_secret_key
```

---

# 🚀 Deployment Steps

## Clone Repository

```bash
git clone <repository-url>
cd project-folder
```

## Install Dependencies

```bash
npm install
pip install -r requirements.txt
```

## Start Frontend

```bash
npm start
```

## Run Backend

```bash
python app.py
```

---

# 📊 Monitoring & Logging

Implemented using:

* AWS CloudWatch Logs
* CloudWatch Metrics
* CloudWatch Alarms

Monitors:

* Lambda Errors
* API Failures
* CPU Usage
* Database Performance

---

# 🔒 Security Features

* JWT Authentication
* Environment Variable Secrets
* API Authorization
* IAM Policies
* HTTPS Support

---

# 📈 Scalability Advantages

✅ Fully Serverless
✅ Auto Scaling
✅ Cost Efficient
✅ High Availability
✅ Fault Tolerant
✅ Low Maintenance

---

# 🧪 Future Enhancements

* Email Notifications
* SMS Alerts
* Event Analytics Dashboard
* Kubernetes Deployment
* CI/CD Pipeline
* Multi-user Roles

---

# 👨‍💻 Author

## Gourav Singh

### Connect With Me

* GitHub: https://github.com/gouravsingh7217
* LinkedIn: https://linkedin.com/in/gouravsingh7217

---

# ⭐ If You Like This Project

Give this repository a ⭐ on GitHub and support the project!
