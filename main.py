import asyncio
import os
import logging
from fastapi import FastAPI, Request, BackgroundTasks, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from pyrogram import Client
from pyrogram.enums import ChatType
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PasswordHashInvalid, FloodWait
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI App
app = FastAPI()

# HTML Templates
templates = Jinja2Templates(directory="templates")

# Configuration
API_ID = int(os.getenv("MY_API_ID"))
API_HASH = os.environ.get("MY_API_KEY")
SESSION_NAME = "temp_session"

# In-memory storage for clients
clients_store = {}
# List of pro users (example)
PRO_USERS = ["+1234567890", "+94775992335"]  # Replace with actual pro user phone numbers

@app.get("/")
async def index(request: Request):
    """ Showing The Main Page """
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/send_code")
async def send_code(phone: str = Form(...)):
    """ Send Telegram OTP """
    if not phone or not phone.startswith('+'):
        raise HTTPException(status_code=400, detail="Invalid phone number format")
    
    client = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH, in_memory=True)
    try:
        await client.connect()
        sent_code = await client.send_code(phone)
        clients_store[phone] = {"client": client, "hash": sent_code.phone_code_hash}
        logger.info(f"OTP sent to {phone}")
        return {"status": "success"}
    except FloodWait as e:
        logger.warning(f"Flood wait for {phone}: {e}")
        return JSONResponse(status_code=429, content={"status": "error", "message": f"Too many requests. Wait {e.value} seconds."})
    except Exception as e:
        logger.error(f"Error sending code to {phone}: {e}")
        return JSONResponse(status_code=400, content={"status": "error", "message": "Failed to send code. Please check your phone number."})

@app.post("/login")
async def login(phone: str = Form(...), code: str = Form(...), password: str = Form(None)):
    """ OPT and the 2FA Password (if needed) """
    if phone not in clients_store:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Session expired. Please restart."})
    
    client = clients_store[phone]["client"]
    phone_hash = clients_store[phone]["hash"]

    try:
        # OTP Verification
        await client.sign_in(phone, phone_hash, code)
        return {"status": "success", "is_pro": phone in PRO_USERS}
    
    except SessionPasswordNeeded:
        # If 2FA is enabled, check for password
        if password:
            try:
                await client.check_password(password)
                return {"status": "success", "is_pro": phone in PRO_USERS}
            except PasswordHashInvalid:
                return JSONResponse(status_code=400, content={"status": "error", "message": "Wrong 2FA Password!"})
        return JSONResponse(status_code=200, content={"status": "2fa_needed"})
    
    except PhoneCodeInvalid:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid OTP Code!"})
    
    except Exception as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})

@app.get("/get_chats")
async def get_chats(phone: str):
    """ Get list of groups and channels """
    if phone not in clients_store:
        return {"groups": [], "channels": []}
    
    client = clients_store[phone]["client"]
    groups, channels = [], []
    
    try:
        async for dialog in client.get_dialogs():
            chat = dialog.chat
            info = {"id": str(chat.id), "title": chat.title or "Deleted Account"}
            
            if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                groups.append(info)
            elif chat.type == ChatType.CHANNEL:
                channels.append(info)
                
        logger.info(f"Retrieved {len(groups)} groups and {len(channels)} channels for {phone}")
        return {"groups": groups, "channels": channels}
    except Exception as e:
        logger.error(f"Error getting chats for {phone}: {e}")
        return JSONResponse(status_code=500, content={"message": "Failed to load chats. Please try again."})

@app.get("/get_progress")
async def get_progress(phone: str):
    """ Get current cleanup progress for a phone number """
    if phone not in clients_store:
        return {"progress": 0, "status": "not_started", "message": "No active session"}
    
    progress_data = clients_store[phone].get("progress", {"progress": 0, "status": "not_started", "message": "Initializing..."})
    return progress_data

@app.post("/start_cleanup")
async def start_cleanup(request: Request, background_tasks: BackgroundTasks):
    """ Start cleanup process in background """
    data = await request.json()
    phone = data.get("phone")
    keep_ids = data.get("keep_ids", [])
    
    if not phone or phone not in clients_store:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid session"})
    
    # Initialize progress tracking
    clients_store[phone]["progress"] = {"progress": 0, "status": "starting", "message": "Initializing cleanup..."}
    
    background_tasks.add_task(run_cleaning, keep_ids, phone)
    logger.info(f"Started cleanup for {phone}, keeping {len(keep_ids)} chats")
    return {"status": "success"}

async def run_cleaning(keep_ids, phone):
    """ Perform cleanup and logout """
    if phone not in clients_store:
        return
        
    client = clients_store[phone]["client"]
    
    try:
        # First, count total chats to process
        total_to_leave = 0
        async for dialog in client.get_dialogs():
            if str(dialog.chat.id) not in keep_ids:
                total_to_leave += 1
        
        if total_to_leave == 0:
            # No chats to leave
            clients_store[phone]["progress"] = {"progress": 100, "status": "completed", "message": "No groups to leave!"}
            logger.info(f"No cleanup needed for {phone}")
            return
        
        # Update progress: starting
        clients_store[phone]["progress"] = {"progress": 0, "status": "processing", "message": f"Found {total_to_leave} groups to leave"}
        
        left_count = 0
        
        # Process each chat
        async for dialog in client.get_dialogs():
            if str(dialog.chat.id) not in keep_ids:
                try:
                    await client.leave_chat(dialog.chat.id)
                    left_count += 1
                    
                    # Update progress
                    progress_percent = int((left_count / total_to_leave) * 100)
                    clients_store[phone]["progress"] = {
                        "progress": progress_percent, 
                        "status": "processing", 
                        "message": f"Left {left_count}/{total_to_leave} groups"
                    }
                    
                    await asyncio.sleep(1.2)  # Prevent flood
                except Exception as e:
                    logger.warning(f"Failed to leave chat {dialog.chat.id}: {e}")
                    await asyncio.sleep(5)  # Longer wait on error
        
        # Update progress: terminating sessions
        clients_store[phone]["progress"] = {"progress": 95, "status": "finalizing", "message": "Terminating all sessions..."}
        
        logger.info(f"Cleanup complete for {phone}: left {left_count} chats")
        
        # Terminate all sessions (including main Telegram app) for security
        terminated_sessions = False
        try:
            # Try terminate_sessions first
            await client.terminate_sessions()
            terminated_sessions = True
            logger.info(f"Terminated all sessions for {phone}")
        except AttributeError:
            # If method doesn't exist, try alternative approach
            logger.warning(f"terminate_sessions not available, trying alternative...")
            try:
                # Try using invoke with raw API
                from pyrogram.raw.functions import auth
                await client.invoke(auth.ResetAuthorizations())
                terminated_sessions = True
                logger.info(f"Terminated all sessions using raw API for {phone}")
            except Exception as e2:
                logger.warning(f"Raw API terminate also failed for {phone}: {e2}")
        except Exception as e:
            logger.warning(f"Failed to terminate sessions for {phone}: {e}")
            # Try alternative if main method fails
            try:
                from pyrogram.raw.functions import auth
                await client.invoke(auth.ResetAuthorizations())
                terminated_sessions = True
                logger.info(f"Terminated all sessions using fallback method for {phone}")
            except Exception as e2:
                logger.warning(f"Fallback terminate also failed for {phone}: {e2}")
        
        # Update progress: logging out
        clients_store[phone]["progress"] = {"progress": 98, "status": "finalizing", "message": "Logging out..."}
        
        # Always try to log out the bot session
        logged_out = False
        try:
            if client.is_connected:
                await client.log_out()
                logged_out = True
                logger.info(f"Logged out bot session for {phone}")
            else:
                logger.warning(f"Client not connected for {phone}, cannot log out")
        except Exception as e:
            logger.error(f"Failed to log out bot session for {phone}: {e}")
            # Try force disconnect
            try:
                await client.disconnect()
                logged_out = True
                logger.info(f"Force disconnected bot session for {phone}")
            except Exception as e2:
                logger.error(f"Failed to force disconnect for {phone}: {e2}")
        
        # Update completion message based on what actually happened
        if terminated_sessions and logged_out:
            completion_msg = "Cleanup completed successfully! All sessions terminated and bot logged out."
        elif terminated_sessions:
            completion_msg = "Cleanup completed! All sessions terminated (bot session may still be active)."
        elif logged_out:
            completion_msg = "Cleanup completed! Bot logged out (other sessions may still be active)."
        else:
            completion_msg = "Cleanup completed! Please manually log out from Telegram for security."
        
        # Update progress: completed
        clients_store[phone]["progress"] = {"progress": 100, "status": "completed", "message": completion_msg}
        logger.info(f"Set progress to completed for {phone}")
            
    except Exception as e:
        logger.error(f"Error during cleanup for {phone}: {e}")
        clients_store[phone]["progress"] = {"progress": 0, "status": "error", "message": "Cleanup failed. Please try again."}
    finally:
        # Delay cleanup to allow frontend to see completion status
        async def delayed_cleanup():
            await asyncio.sleep(10)  # Keep data for 10 seconds
            clients_store.pop(phone, None)
        
        asyncio.create_task(delayed_cleanup())

@app.get("/admin/users")
async def get_all_active_users():
    return {"active_sessions": list(clients_store.keys()), "pro_users": PRO_USERS}

@app.post("/admin/add_pro")
async def add_pro_user(phone: str):
    if phone not in PRO_USERS:
        PRO_USERS.append(phone)
    return {"message": f"{phone} is now a PRO user"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)