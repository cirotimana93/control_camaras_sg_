import base64
import os
from typing import List, Tuple, Union, Optional
import requests
from msal import ConfidentialClientApplication
from src.config import Config

def sendMailOffice365(
    sender: str,
    subject: str,
    messageBody: str,
    recipients: List[str],
    attachments: Optional[List[Union[str, Tuple[str, bytes]]]] = None
) -> bool:
    try:
        clientId = Config.GRAPH_CLIENT_ID
        clientSecret = Config.GRAPH_CLIENT_SECRET
        tenantId = Config.GRAPH_TENANT_ID
        senderEmail = sender or Config.EMAIL_EMISOR
        
        if not all([clientId, clientSecret, tenantId, senderEmail]):
            print("[error] configuracion de graph api incompleta para envio de correos")
            return False

        # autenticacion con graph api
        app = ConfidentialClientApplication(
            client_id=clientId,
            client_credential=clientSecret,
            authority=f"https://login.microsoftonline.com/{tenantId}"
        )
        
        authResult = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" not in authResult:
            print(f"[error] error obteniendo token: {authResult.get('error_description')}")
            return False
            
        token = authResult["access_token"]
        
        # destinatarios
        toRecipients = [{"emailAddress": {"address": email.strip()}} for email in recipients if email.strip()]
        
        # adjuntos en memoria o archivo
        preparedAttachments = []
        if attachments:
            for item in attachments:
                if isinstance(item, tuple):
                    fileName, fileContent = item
                    if isinstance(fileContent, str):
                        fileContent = fileContent.encode("utf-8")
                    preparedAttachments.append({
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": fileName,
                        "contentBytes": base64.b64encode(fileContent).decode("utf-8")
                    })
                else:
                    with open(item, "rb") as f:
                        fileContent = f.read()
                    preparedAttachments.append({
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": os.path.basename(item),
                        "contentBytes": base64.b64encode(fileContent).decode("utf-8")
                    })
                    
        message = {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": messageBody
            },
            "toRecipients": toRecipients
        }
        
        if preparedAttachments:
            message["attachments"] = preparedAttachments
            
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        url = f"https://graph.microsoft.com/v1.0/users/{senderEmail}/sendMail"
        response = requests.post(url, headers=headers, json={"message": message}, timeout=30)
        
        if response.status_code == 202:
            print(f"[ok] correo enviado exitosamente a: {', '.join(recipients)}")
            return True
        else:
            print(f"[error] error enviando correo: {response.status_code} - {response.text}")
            return False
            
    except Exception as error:
        print(f"[error] excepcion en sendMailOffice365: {str(error)}")
        return False
