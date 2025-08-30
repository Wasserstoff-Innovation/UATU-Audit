from typing import List, Optional, Dict
from pydantic import BaseModel

class FlowFunction(BaseModel):
    name: str
    visibility: Optional[str] = None
    mutability: Optional[str] = None
    inputs: List[Dict] = []
    outputs: List[Dict] = []
    modifiers: List[str] = []
    events_emitted: List[str] = []

class FlowContract(BaseModel):
    name: str
    visibility: Optional[str] = None
    inherits: List[str] = []
    state_vars: List[Dict] = []
    functions: List[FlowFunction] = []
    events: List[Dict] = []

class Flows(BaseModel):
    contracts: List[FlowContract] = []

class JourneyStep(BaseModel):
    contract: str
    function: str
    actor: str

class Journey(BaseModel):
    id: str
    tags: List[str] = []
    chain: Optional[str] = None
    steps: List[JourneyStep]

class Journeys(BaseModel):
    journeys: List[Journey] = []

class Threats(BaseModel):
    by_function: Dict[str, Dict[str, List[str]]] = {}
    by_journey: Dict[str, Dict[str, List[str]]] = {}
