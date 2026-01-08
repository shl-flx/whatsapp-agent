import os
import logging
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whatsapp-webhook")

app = FastAPI(title="WhatsApp Webhook - Phase 1")

@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    logger.info(f"VERIFY → mode={hub_mode}, token={hub_verify_token}")
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")

@app.post("/webhook")
async def receive_webhook(request: Request):
    payload = await request.json()
    logger.info(f"WEBHOOK RECEIVED: {payload}")
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"status": "running"}
