const jwt = require("jsonwebtoken");

exports.handler = async (event) => {

    try {

        const token = event.authorizationToken.split(" ")[1];

        const decoded = jwt.verify(
            token,
            process.env.JWT_SECRET
        );

        return {
            principalId: decoded.id,
            policyDocument: {
                Version: "2012-10-17",
                Statement: [
                    {
                        Action: "execute-api:Invoke",
                        Effect: "Allow",
                        Resource: event.methodArn
                    }
                ]
            }
        };

    } catch (err) {

        throw new Error("Unauthorized");

    }

};