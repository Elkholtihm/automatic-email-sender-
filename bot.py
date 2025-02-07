from groq import Groq
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import base64
from dotenv import load_dotenv

# -----------------------------------------write email using LLM---------------------------
# Function to write the email using Groq API
def write_email(job_description, groq_key):
    client = Groq(api_key=groq_key)
    # Get the email content
    completion = client.chat.completions.create(
        model="gemma2-9b-it",
        messages=[
            {
                'role': 'user',
                'content': f''' 
                Please, this is an automatic system to write emails and send them. I need you to write an email to apply for an internship. Here is the information to include in the email:

                * I am Hamza Kholti, a student at ENSA Tetouan in Data Science, Big Data, and AI.

                * I am looking for a PFA internship.

                * and say "Please find my GitHub, portfolio and resume in attachement"

                Here is the job description : {job_description}
                I need you to show my interest in a PFA internship.
                The job description might include a job opportunity PFE or PFA : 
                - if it a PFA opportunity or the type of the intership is not provided or it says it is a summer intership, please say 'regarding the internship advertisement you published' 
                - if it is a PFE internship just write an email to apply without indicating that the application is regarding the advertisement published because i just use the email to apply. despite the opportunity doesnt fit me.
                Please note that this is an automatic system. Provide only the email and nothing else, as everything you generate will be copied, pasted, and sent directly to the email.
                please i want the email to be short.
                please provide only the body without the the object.
                ''',
            }
        ],
        temperature=0.6,
        max_tokens=650,
        top_p=1,
        stream=True,
        stop=None,
    )
    email_content = ""
    for chunk in completion:
        if chunk.choices[0].delta.content:
            email_content += chunk.choices[0].delta.content

    # Get the email subject
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                'role': 'user',
                'content': f''' 
                Please, this is an automatic system to write emails and send them. i already write the body of the email. I need you to give me only the subject of the email.
                Here is the job description : {job_description}
                please thats the rules to follow : 
                use object provided in job_description if its related to data, and AI and it is a PFA intership (not a PFE intership)
                if not provided, say 'apply for intership'.
                i want it to be short.
                Please note that this is an automatic system. Provide only the subject of the email and nothing else, as everything you generate will be copied, pasted, and sent directly to the email.
                ''',
            }
        ],
        temperature=1,
        max_tokens=650,
        top_p=1,
        stream=True,
        stop=None,
    )
    email_subject = ""
    for chunk in completion:
        if chunk.choices[0].delta.content:
            email_subject += chunk.choices[0].delta.content

    return email_subject, email_content


# -------------------------------------send email----------------------------------------
# Load environment variables
load_dotenv()
CREDENTIALS_FILE = os.getenv("CREDENTIALS_FILE", "credentials_local.json")
TOKEN_FILE = os.getenv("TOKEN_FILE", "token.json")

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def authenticate_gmail():
    """Authenticate and return the Gmail API service."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    # Disable cache_discovery to suppress the warning
    return build('gmail', 'v1', credentials=creds, cache_discovery=False)


def create_message_with_attachment(sender, to, subject, body, attachment_path=None):
    """Create a message with an optional attachment."""
    message = MIMEMultipart()
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject

    # Attach the email body
    message.attach(MIMEText(body))

    # Attach the file if provided
    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename={os.path.basename(attachment_path)}",
        )
        message.attach(part)

    return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}


def send_email(to_email, sender, subject, body, attachment_path=None):
    """Send an email with an optional attachment using the Gmail API."""
    try:
        # Authenticate and create the Gmail API service
        service = authenticate_gmail()

        # Create the email message
        message = MIMEMultipart()
        message['to'] = to_email
        message['from'] = sender
        message['subject'] = subject

        # Create an HTML body that includes the GitHub link
        html_body = f"""
        <html>
            <body>
                <p>{body}</p>
                <p>Check out my <a href="https://my-portfolio-96kn.onrender.com" target="_blank">portfolio</a>.</p>
                <p>Check out my <a href="https://github.com/Elkholtihm" target="_blank">GitHub Profile</a>.</p>
            </body>
        </html>
        """
        message.attach(MIMEText(html_body, "html"))

        # Attach the CV file if provided
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={'hamza_kholti_cv.pdf'}",
            )
            message.attach(part)

        # Send the email
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        sent_message = service.users().messages().send(userId="me", body={'raw': raw_message}).execute()
        print(f"Email sent! Message ID: {sent_message['id']}")
    except Exception as e:
        print(f"An error occurred: {e}")
