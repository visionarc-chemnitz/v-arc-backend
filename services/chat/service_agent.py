# import os
# import uuid
# from .agent_tools import AgentToolService
# from langchain_core.messages import (
#     SystemMessage,
#     ToolMessage,
#     RemoveMessage,
#     HumanMessage,
#     AIMessage,
# )
# from langgraph.graph import StateGraph, START, END
# from langgraph.types import Command, interrupt
# from typing import Literal, TypedDict
# from ..state import StateService
# from langchain_groq import ChatGroq

# from rich.console import Console

# from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
# from psycopg import AsyncConnection

# from .prompts import (
#     ARC42_GENERATION_PROMPT,    
# )

# from dotenv import load_dotenv

# load_dotenv()

# class ChatConfig(TypedDict):
#     thread_id: str
#     recursion_limit: int
#     checkpoint_ns: str
#     checkpoint_id: str


# class ChatConfigWrapper(TypedDict):
#     configurable: ChatConfig


# class ChatService:
#     def __init__(self, groq_api_key: str):
#         self.llm = ChatGroq(
#             groq_api_key=groq_api_key,
#             model="deepseek-r1-distill-llama-70b-specdec",
#             temperature=0.8,
#             max_tokens=None, 
#             timeout=None,
#             max_retries=2,
#             streaming=True,
            
#         )
#         self.memory = None
#         self.app = None
        
#         self.agent_tool_service = AgentToolService()
        
#         # Augment the LLM with tools
#         self.tools = self.agent_tool_service.tools
#         self.tools_by_name = self.agent_tool_service.tools_by_name
#         self.llm_with_tools = self.llm.bind_tools(self.tools)

#     async def init_memory(self):
#         """Initialize the memory with AsyncPostgresSaver"""
#         conn_string = os.getenv("DB_URI")
#         if not conn_string:
#             raise ValueError("DB_URI environment variable not set")
#         connection_kwargs = {
#             "autocommit": True,
#             "prepare_threshold": 0,
#         }
#         try:
#             self.conn = await AsyncConnection.connect(conn_string, **connection_kwargs)
#             self.memory = AsyncPostgresSaver(self.conn)
#             return self.memory
#         except Exception as e:
#             if hasattr(self, "conn"):
#                 await self.conn.close()
#                 raise RuntimeError(
#                     f"Failed to initialize database connection: {str(e)}"
#                 ) from e

#     # __call__ method is used to make the class callable (awaitable)
#     async def __call__(self, *args, **kwds):
#         try:
#             # create the workflow
#             workflow = self.create_workflow()
#             self.memory = await self.init_memory()
            
#             await self.memory.setup()

#             # Compile the workflow
#             self.app = workflow.compile(checkpointer=self.memory)

#             return self.app
#         except Exception as e:
#             print(f"Error in workflow execution: {e}")
#             raise

#     def create_workflow(self):
#         workflow = StateGraph(StateService)

#         # Add nodes
#         workflow.add_node("llm_call", self.llm_call)
#         workflow.add_node("environment", tool_node)
        
#         # Add edges
#         workflow.add_edge(START, "llm_call")
#         workflow.add_conditional_edges(
#             "llm_call",
#             self.should_continue,
#             {
#                 # Name returned by should_continue : Name of next node to visit
#                 "Action": "environment",
#                 END: END,
#             },
#         )
#         workflow.add_edge("environment", "llm_call")

#         return workflow

#     async def get_thread_config(self, thread_id: str) -> ChatConfigWrapper:
#         """Get the configuration for a specific thread ID."""
#         return {
#             "configurable": {
#                 "thread_id": thread_id,
#                 "checkpoint_ns": "",
#                 "checkpoint_id": str(uuid.uuid4()),
#                 "recursion_limit": os.getenv("RECURSION_LIMIT"),
#             }
#         }


# # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#     # workflow node handlers 
# # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#     def llm_call(self, state: StateService):
#         """LLM decides whether to call a tool or not"""

#         return {
#             "messages": [
#                 self.llm_with_tools.invoke(
#                     [
#                         SystemMessage(
#                             content="You are a helpful assistant tasked with performing arithmetic on a set of inputs."
#                         )
#                     ]
#                     + state["messages"]
#                 )
#             ]
#         }


#     def tool_node(self, state: StateService):
#         """Performs the tool call"""

#         result = []
#         for tool_call in state["messages"][-1].tool_calls:
#             tool = self.tools_by_name[tool_call["name"]]
#             observation = tool.invoke(tool_call["args"])
#             result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
#         return {"messages": result}


#     # Conditional edge function to route to the tool node or end based upon whether the LLM made a tool call
#     def should_continue(self, state: StateService) -> Literal["environment", END]:
#         """Decide if we should continue the loop or stop based upon whether the LLM made a tool call"""

#         messages = state["messages"]
#         last_message = messages[-1]
#         # If the LLM makes a tool call, then perform an action
#         if last_message.tool_calls:
#             return "Action"
#         # Otherwise, we stop (reply to the user)
#         return END

# # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#     # Processing message through the workflow and streaming the response
# # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


#     async def get_thread_history(self, config: ChatConfigWrapper, value: str):
#         """Get message history with connection management."""
#         try:
#             if not self.app:
#                 await self.__call__()

#             thread_config = {
#                 "configurable": {
#                     "thread_id": config["configurable"]["thread_id"],
#                 }
#             }

#             state = await self.app.aget_state(thread_config)

#             if not state:
#                 return None

#             if value == "history":
#                 return state.values if hasattr(state, "values") else None
#             elif value == "tasks":
#                 if hasattr(state, "tasks") and state.tasks:
#                     if len(state.tasks) > 0 and hasattr(state.tasks[0], "interrupts"):
#                         return state.tasks[0].interrupts
#             return None

#         except Exception as e:
#             print(f"Error retrieving thread: {e}")
#             return None

#     async def process_message(self, message: str, config: ChatConfigWrapper):
#         """Process a message through the workflow and stream the response."""
#         try:
#             if not self.app:
#                 await self.__call__()

#             last_state = await self.get_thread_history(config, "history")

#             task = await self.get_thread_history(config, "tasks")
#             if task is not None:
#                 human_in_loop_dict: dict = last_state.get("human_in_loop", {})

#                 for k, v in human_in_loop_dict.items():
#                     if v is None:
#                         current_question = k
#                         break

#                 if current_question:
#                     human_in_loop_dict[current_question] = message
#                     state_to_update = StateService(
#                         messages=last_state.get("messages", [])
#                         + [
#                             AIMessage(content=current_question),
#                             HumanMessage(content=message),
#                         ],
#                         category=last_state.get("category"),
#                         questions=last_state.get("questions", []),
#                         context=last_state.get("context", ""),
#                         human_in_loop=human_in_loop_dict,
#                         next_step="human",
#                         is_interrupted=last_state.get("is_interrupted", False),
#                         summary=last_state.get("summary", ""),
#                         scenario=last_state.get("scenario", ""),
#                         can_proceed=last_state.get("can_proceed", False),
#                         bpmn_xml=last_state.get("bpmn_xml", None),
#                     )

#                     # await self.app.aupdate_state(config, state_to_update)
#                     # updated_state = await self.get_thread_history(config, "history")
#                     # rich.print("==========================================================")
#                     # rich.print(f"State updated: {updated_state}")
#                     # rich.print("==========================================================")

#                     # Update messages with the answer
#                     # messages = last_state.get('messages', [])
#                     # messages.append(HumanMessage(content=message))

#                     # # Resume with updated state
#                     # resume_state = {
#                     #     "messages": messages,
#                     #     "human_in_loop": human_in_loop_dict,
#                     #     "questions": last_state.get('questions', []),
#                     #     "context": last_state.get('context', ''),
#                     #     "is_interrupted": True,  # Keep true until all questions answered
#                     #     "category": last_state.get('category'),
#                     #     "current_question": None  # Clear current question
#                     # }
#                     """ rich.print("==========================================================")
#                 rich.print("")
#                 rich.print("Resuming workflow with updated state")
#                 rich.print("")
#                 rich.print("==========================================================") """
#                     # async for step in self.app.astream(
#                     #     Command(resume=message, update=state_to_update, goto="human"),
#                     #     config=config,
#                     #     stream_mode="updates"
#                     # ):
#                     #     yield await self.process_step(step, config)
#                     # return

#                     async with self._lock:
#                         async for step in self.app.astream(
#                             Command(resume=message, update=state_to_update),
#                             config=config,
#                             stream_mode="updates",
#                         ):
#                             yield await self.process_step(step, config)
#                         return

#             if last_state:
#                 state = last_state
#                 state["messages"].append(HumanMessage(content=message))
#             else:
#                 state = StateService(
#                     messages=[HumanMessage(content=message)],
#                     category=None,
#                     next_step=None,
#                     human_in_loop={},
#                     questions=None,
#                     is_interrupted=False,
#                     context=None,
#                     summary=None,
#                     scenario=None,
#                     can_proceed=False,
#                     # functional_requirements=[],
#                     # nonfunctional_requirements=[],
#                     gathered_info=None,
#                     bpmn_xml=None,
#                 )

#             async for step in self.app.astream(state, config, stream_mode="updates"):
#                 yield await self.process_step(step, config)

#         except Exception as e:
#             print(f"Error in process_message: {e}")
#             return f"Error: {str(e)}"
            
#     async def process_step(self, step, config: ChatConfigWrapper):
#         """Process a single step from the workflow stream."""

#         # Get first key from step dict
#         parent_key = next(iter(step))

#         # Handle interrupt case
#         if parent_key == "__interrupt__":
#             question = (
#                 step[parent_key].value
#                 if hasattr(step[parent_key], "value")
#                 else step[parent_key][0].value
#             )
#             return question

#         # Handle BPMN XML case
#         if isinstance(step[parent_key], dict) and "bpmn_xml" in step[parent_key]:
#             bpmn_xml = step[parent_key]["bpmn_xml"]
#             return bpmn_xml

#         # Handle messages case
#         if isinstance(step[parent_key], dict) and "messages" in step[parent_key]:
#             step = step[parent_key]
#             if "messages" in step and step["messages"]:
#                 if isinstance(step["messages"][-1], AIMessage):
#                     return step["messages"][-1].content

#         return None

#     async def generate_arc42_doc(self, config: ChatConfigWrapper):
#         """Generate an arc42 document based on the context."""
#         try:
#             if not self.app:
#                 await self.__call__()

#             # Get the thread history
#             state = await self.get_thread_history(config, "history")

#             if not state:
#                 raise Exception("No thread history found")

#             # Extract required information
#             gathered_info = state.get("gathered_info", "")
#             context = state.get("context", "")

#             # Generate the arc42 document
#             bpmn_prompt = ARC42_GENERATION_PROMPT.format(
#                 context=context, gathered_info=gathered_info
#             )
#             system_prompt = SystemMessage(content=bpmn_prompt)
#             response = self.llm.invoke(system_prompt.content)
#             return response.content

#         except Exception as e:
#             print(f"Error generating arc42 document: {e}")
#             return None
