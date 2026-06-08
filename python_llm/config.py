import os
from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")




DB_HOST     = "localhost"           
DB_PORT     = 3306
DB_USER     = "root"                
DB_PASSWORD = "Iphone13#2006"  
DB_NAME     = "eventpulse"

JWT_SECRET  = "change_this_to_a_long_random_string_abc123xyz"


AWS_REGION      = "ap-south-1"
SNS_TOPIC_ARN   = "arn:aws:sns:ap-south-1:YOUR_ACCOUNT_ID:eventpulse-announcements"

