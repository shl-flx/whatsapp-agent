import os
import logging
import httpx
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")      
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")  

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whatsapp-webhook")

app = FastAPI(title="WhatsApp Webhook - Minimal")


@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    logger.info(f"VERIFY → mode={hub_mode}, token={hub_verify_token}")
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403)


@app.post("/webhook")
async def receive_webhook(request: Request):
    payload = await request.json()
    logger.info(f"WEBHOOK RECEIVED: {payload}")
    
   
    try:
        message = payload["entry"][0]["changes"][0]["value"]["messages"][0]
        sender = message["from"]
        text = message.get("text", {}).get("body", "")
        
        await send_text_message(sender, f"You said: {text}")
    except (KeyError, IndexError):
        pass  
    
    return {"status": "ok"}



async def send_text_message(to: str, text: str):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
    logger.info(f"SENT: {response.json()}")
    return response.json()


@app.get("/")
async def root():
    return {"status": "running"}