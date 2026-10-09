from uuid import UUID
from pydantic import BaseModel, Field
class MessageRequest(BaseModel): session_token:str=Field(min_length=20,max_length=100); run_id:UUID; message:str=Field(min_length=1,max_length=4000)
class SecureRequest(BaseModel): session_token:str=Field(min_length=20,max_length=100); run_id:UUID; root_cause:str|None=Field(default=None,max_length=100); controls:dict[str,dict[str,bool]]|None=None
