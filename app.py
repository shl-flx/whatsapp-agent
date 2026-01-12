import os
import logging
import httpx
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")      
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")  
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whatsapp-webhook")

app = FastAPI(title="WhatsApp Webhook - Minimal")

openai_client = OpenAI(api_key=OPENAI_API_KEY)




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


async def get_ai_response(user_message: str) -> str:
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "You are a helpful WhatsApp assistant. Keep responses brief and friendly."},
                {"role": "user", "content": user_message}
            ],
            max_tokens=150, 
            temperature=0.7
        )
        
        
        prompt_cost = (response.usage.prompt_tokens / 1_000_000) * 0.80
        completion_cost = (response.usage.completion_tokens / 1_000_000) * 3.20
        total_cost = prompt_cost + completion_cost

        logger.info(f"OpenAI Usage - Prompt: {response.usage.prompt_tokens} tokens, "
                    f"Completion: {response.usage.completion_tokens} tokens, "
                    f"Total: {response.usage.total_tokens} tokens")
        logger.info(f"Cost: ${total_cost:.6f} (Prompt: ${prompt_cost:.6f}, Completion: ${completion_cost:.6f})")
        
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"OpenAI Error: {type(e).__name__}: {e}")
        return "Sorry, I'm having trouble connecting to my brain right now. Please try again in a moment!"



@app.post("/webhook")
async def receive_webhook(request: Request):
    payload = await request.json()
    logger.info(f"WEBHOOK RECEIVED: {payload}")
    
   
    try:
        message = payload["entry"][0]["changes"][0]["value"]["messages"][0]
        sender = message["from"]
        text = message.get("text", {}).get("body", "")
        ai_response = await get_ai_response(text)
        await send_text_message(sender, ai_response)
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
