import os

# import fastapi modules
from fastapi import FastAPI, HTTPException, status, Request
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

# import services
from services import ChatService

# import json
import json

# load environment variables
from dotenv import load_dotenv
load_dotenv()

# create FastAPI app
app = FastAPI()

# allowed origins
origins = [
  "https://v-arc.vercel.app",
]

# cors middleware
app.add_middleware(
  CORSMiddleware,
  allow_origins=[*],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)


# endpoint to check the status of the backend
@app.get("/")
def check_status():
  return JSONResponse(
    content={ "status_code": status.HTTP_200_OK, "message": "Backend FastAPI is running" }
  )

# instantiate the chat service
chat_service = ChatService(
    groq_api_key=os.getenv("GROQ_API_KEY"),
)

# endpoint to start a chat session
# supports server-sent events (SSE)
@app.post("/chat")
async def chat_endpoint(request: Request):
    try:
        # Parse the request body
        body = await request.json()
        message = body.get("message", "").strip()
        thread_id = body.get("thread_id", "").strip()
        # xml = body.get("xml", "").strip()

        if not message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message is required"
            )
        
        if not thread_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Thread ID is required"
            )

        async def generate():
            try:
                config = await chat_service.get_thread_config(thread_id)
                
                print(f"request: {body} config: {config}, message: {message}")
                
                # Parse the xml - fetch comments and return those comments then ask use to confirm if he want to update xml based on those comments.
                # if yes then trigger the whole generation again but with different prompts.

                async for chunk in chat_service.process_message(message, config):
                  yield f"data: {json.dumps({'response': chunk, 'thread_id': config['configurable']['thread_id']})}\n\n"
                
                # print(f"app response: {await chat_service.get_thread_history(config.get('configurable').get('thread_id'))}")
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post("/thread-history")
async def get_thread_history(request: Request):
  try:
    body = await request.json()
    thread_id = body.get("thread_id", "").strip()
    value = body.get("value", "").strip()
    
    if not thread_id:
      raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Thread ID is required"
      )
      
    config = await chat_service.get_thread_config(thread_id)
    history = await chat_service.get_thread_history(config,value)
    
    if history is None or 'messages' not in history:
      return []
    else :
      messages = [{"role": "assistant" if message.type == "ai" else "user", "content": message.content} for message in history['messages']]
    return messages
    
  except Exception as e:
    print(f"Error: {str(e)}")
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail=str(e)
    )

@app.post("/generate-arc42")
async def generate_arc42(request: Request):
    try:
        # Parse the request body
        body = await request.json()
        thread_id = body.get("thread_id", "").strip()
        
        if not thread_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Thread ID is required"
            )
            
        config = await chat_service.get_thread_config(thread_id)
        
        markdown_content = await chat_service.generate_arc42_doc(config)
        # Convert markdown to HTML
        # html_content = markdown2.markdown(markdown_content)
        
        # # Create temporary file
        # with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w', encoding='utf-8') as tmp:
        #     tmp.write(html_content)
        #     tmp_path = tmp.name
            
        # return FileResponse(
        #     path=tmp_path,
        #     filename="arc42_documentation.html",
        #     media_type="text/html"
        # )

        return markdown_content

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=str(e)
        )
