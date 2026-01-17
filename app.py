import os
import logging
import httpx
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse, HTMLResponse
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")  # was: ACCESS_TOKEN
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")


PAGE_ID = os.getenv("PAGE_ID")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")


INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("unified-webhook")

app = FastAPI(title="Unified Messaging Webhook")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
conversation_memory = {}
MAX_HISTORY = 10


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
        obj = payload.get("object")
        
        if obj == "whatsapp_business_account":
            await handle_whatsapp(payload)
        
        elif obj == "page":
            await handle_messenger(payload)
        
        elif obj == "instagram":
            await handle_instagram(payload)
        
        else:
            logger.info(f"Unknown object type: {obj}")
    
    except Exception as e:
        logger.error(f"Error processing webhook: {type(e).__name__}: {e}")
    
    return {"status": "ok"}



async def handle_whatsapp(payload):
    try:
        value = payload["entry"][0]["changes"][0]["value"]
        
        if "messages" not in value:
            logger.info("WhatsApp: Status update (not a message)")
            return
        
        message = value["messages"][0]
        sender = message["from"]
        
        if message.get("type") == "text":
            text = message["text"]["body"]
            logger.info(f"WhatsApp from {sender}: {text}")
            
            ai_response = await get_ai_response(f"wa_{sender}", text)
            await send_whatsapp_message(sender, ai_response)
    
    except (KeyError, IndexError) as e:
        logger.error(f"WhatsApp parsing error: {e}")



async def handle_messenger(payload):
    try:
        messaging = payload["entry"][0].get("messaging", [])
        
        if not messaging:
            return
        
        event = messaging[0]
        sender_id = event["sender"]["id"]
        
        if sender_id == PAGE_ID:
            return
        
        if "message" in event and "text" in event["message"]:
            text = event["message"]["text"]
            logger.info(f"Messenger from {sender_id}: {text}")
            
            ai_response = await get_ai_response(f"fb_{sender_id}", text)
            await send_messenger_message(sender_id, ai_response)
    
    except (KeyError, IndexError) as e:
        logger.error(f"Messenger parsing error: {e}")


async def handle_instagram(payload):
    try:
        messaging = payload["entry"][0].get("messaging", [])
        
        if not messaging:
            return
        
        event = messaging[0]
        sender_id = event["sender"]["id"]
        
        if sender_id == INSTAGRAM_ACCOUNT_ID:
            return
        
        if "message" in event and "text" in event["message"]:
            text = event["message"]["text"]
            logger.info(f"Instagram from {sender_id}: {text}")
            
            ai_response = await get_ai_response(f"ig_{sender_id}", text)
            await send_instagram_message(sender_id, ai_response)
    
    except (KeyError, IndexError) as e:
        logger.error(f"Instagram parsing error: {e}")



async def get_ai_response(user_id: str, user_message: str) -> str:
    try:
        if user_id not in conversation_memory:
            conversation_memory[user_id] = []
        
        conversation_memory[user_id].append({"role": "user", "content": user_message})
        
        if len(conversation_memory[user_id]) > MAX_HISTORY:
            conversation_memory[user_id] = conversation_memory[user_id][-MAX_HISTORY:]
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Keep responses brief and friendly."}
        ] + conversation_memory[user_id]
        
        response = openai_client.chat.completions.create(
            model="gpt-4.1-mini",  
            messages=messages,
            max_tokens=150,
            temperature=0.7
        )
        
        assistant_message = response.choices[0].message.content
        conversation_memory[user_id].append({"role": "assistant", "content": assistant_message})
        
        if len(conversation_memory[user_id]) > MAX_HISTORY:
            conversation_memory[user_id] = conversation_memory[user_id][-MAX_HISTORY:]
        
        prompt_cost = (response.usage.prompt_tokens / 1_000_000) * 0.8
        completion_cost = (response.usage.completion_tokens / 1_000_000) * 3.20
        total_cost = prompt_cost + completion_cost

        logger.info(f"OpenAI: {response.usage.total_tokens} tokens, ${total_cost:.6f}")
        
        return assistant_message
        
    except Exception as e:
        logger.error(f"OpenAI Error: {type(e).__name__}: {e}")
        return "Sorry, I'm having trouble right now. Please try again."



async def send_whatsapp_message(to: str, text: str):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
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
    logger.info(f"WhatsApp SENT: {response.json()}")
    return response.json()



async def send_messenger_message(recipient_id: str, text: str):
    url = f"https://graph.facebook.com/v21.0/{PAGE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {PAGE_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
    logger.info(f"Messenger SENT: {response.json()}")
    return response.json()



async def send_instagram_message(recipient_id: str, text: str):
    url = f"https://graph.instagram.com/v21.0/{INSTAGRAM_ACCOUNT_ID}/messages"
    headers = {
        "Authorization": f"Bearer {INSTAGRAM_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
    logger.info(f"Instagram SENT: {response.json()}")
    return response.json()




@app.get("/privacy")
async def privacy():
    return HTMLResponse("""
    <html>
    <head><title>Privacy Policy</title></head>
    <body>
        <h1>Privacy Policy</h1>
        <p>This app collects messages you send to provide AI-powered responses.</p>
        <p>We do not share your data with third parties.</p>
        <p>Contact: sahlebrahim@yahoo.com</p>
    </body>
    </html>
    """)

@app.get("/terms")
async def terms():
    return HTMLResponse("""
    <html>
    <head><title>Terms of Service</title></head>
    <body>
        <h1>Terms of Service</h1>
        <p>By using this service, you agree to receive AI-generated responses.</p>
        <p>This service is provided as-is for testing purposes.</p>
    </body>
    </html>
    """)

@app.get("/data-deletion")
async def data_deletion():
    return HTMLResponse("""
    <html>
    <head><title>Data Deletion</title></head>
    <body>
        <h1>Data Deletion Request</h1>
        <p>To request deletion of your data, email: sahlebrahim@yahoo.com</p>
    </body>
    </html>
    """)




@app.get("/")
async def root():
    return {"status": "running", "platforms": ["whatsapp", "messenger", "instagram"]}