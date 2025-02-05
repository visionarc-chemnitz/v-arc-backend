from langchain_core.tools import tool
from ..state import StateService

class AgentToolService:
    def __init__(self):
        self.tools = [self.vaidate_xml,self.search_web]
        self.tools = []
        self.tools_by_name = {tool.name: tool for tool in self.tools}
        self.state_service = StateService()

    @tool
    def vaidate_xml(self, xml: str) -> str:
        pass


    @tool
    def search_web(self, topic: str) -> str:
        pass