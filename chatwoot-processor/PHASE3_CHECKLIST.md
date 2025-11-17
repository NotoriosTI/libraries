# Phase 3.1 Implementation Checklist — Purchase Expert Agent (Agent-as-Tool Pattern)

**Project:** deploy-juan  
**Phase:** 3.1 — Purchase Expert Foundation  
**Status:** 🚧 In Progress  
**Prerequisites:** ✅ Phase 1-2 Complete, existing `production_expert` as reference  
**Architecture:** Use `create_react_agent` with agent-as-tool pattern (NO custom graphs)

---

## ⚠️ Critical Architectural Constraints

**MUST FOLLOW existing patterns from `production_expert`:**

1. ✅ **Use prebuilt `create_react_agent`** — NO custom StateGraph implementations
2. ✅ **Agent-as-tool pattern** — Any sub-agent MUST be wrapped as a `@tool` 
3. ✅ **Response models** — Use Pydantic models with `response_format` parameter
4. ✅ **Lazy initialization** — Database/API clients initialized on first use
5. ✅ **Tool-based composition** — Import tools from other experts (e.g., `query_database`)

**Reference implementation:** `/Users/bastianibanez/work/deploy-juan/src/juan/production_expert/`

---

## 📋 Task Group 3.1.1 — Purchase Expert Models & Schemas

**Goal:** Define Pydantic models following `production_models.py` pattern.

- [ ] Create `src/juan/purchase_expert/purchase_models.py`
- [ ] Define `PurchaseResponseModel`:
  ```python
  from pydantic import BaseModel, Field
  from langchain_core.messages import AnyMessage
  from typing import List, Optional
  
  class PurchaseResponseModel(BaseModel):
      answer: str = Field(description="Respuesta al proveedor.")
      continue_conversation: bool = Field(
          description="Indica si se debe continuar con otra acción."
      )
      order_id: Optional[str] = Field(
          None, description="ID de la orden gestionada."
      )
      messages: List[AnyMessage] = Field(
          description="Historial de mensajes."
      )
  ```
- [ ] Define tool argument schemas:
  - `CreatePurchaseQuoteArgs` (provider_id, items, expected_date)
  - `ConfirmPurchaseOrderArgs` (order_id)
  - `CheckOrderStatusArgs` (order_id)
- [ ] Add validation and field descriptions
- [ ] Commit: `feat(phase3): add purchase expert Pydantic models`

---

## 📋 Task Group 3.1.2 — Odoo Purchase Tools (Direct Implementation)

**Goal:** Implement purchase order tools using existing `odoo_manager` pattern.

- [ ] Create `src/juan/purchase_expert/purchase_tools.py`
- [ ] Add lazy initialization following `production_tools.py`:
  ```python
  from juan.common import odoo_manager
  from dev_utils import pretty_logger
  from langchain_core.tools import tool
  
  logger = pretty_logger.PrettyLogger(service_name="purchase_tools")
  
  _purchase_api = None
  
  def _get_purchase_api():
      global _purchase_api
      if _purchase_api is None:
          logger.info("Initializing purchase API client")
          _purchase_api = odoo_manager.get_purchase_client()
      return _purchase_api
  ```
- [ ] Implement core tools:
  - `@tool("create_purchase_quote")` — Creates RFQ in Odoo
  - `@tool("confirm_purchase_order")` — Confirms PO
  - `@tool("check_order_status")` — Retrieves order state
  - `@tool("cancel_purchase_order")` — Cancels order
- [ ] Add `get_purchase_tools()` factory returning tool list
- [ ] Include error handling and logging
- [ ] Commit: `feat(phase3): implement purchase order tools`

---

## 📋 Task Group 3.1.3 — Purchase Agent with create_react_agent

**Goal:** Build agent using `create_react_agent` exactly like `production_agent.py`.

- [ ] Create `src/juan/purchase_expert/purchase_agent.py`
- [ ] Implement following `production_agent.py` structure:
  ```python
  from .purchase_tools import get_purchase_tools
  from .purchase_models import PurchaseResponseModel
  from juan.config import get_llm
  
  from langgraph.prebuilt import create_react_agent
  from langgraph.checkpoint.memory import MemorySaver
  
  purchase_llm = get_llm(
      llm_name="purchase_reasoner",
      llm_model="claude-sonnet-4-5"
  )
  
  tools = get_purchase_tools()
  checkpointer = MemorySaver()
  
  purchase_agent = create_react_agent(
      purchase_llm,
      tools=tools,
      response_format=PurchaseResponseModel,
      checkpointer=checkpointer,
  )
  ```
- [ ] Create `purchase_prompts.py` with system prompts
- [ ] Add `__init__.py` exposing models, tools, prompts
- [ ] Commit: `feat(phase3): create purchase_agent with create_react_agent`

---

## 📋 Task Group 3.1.4 — Integration with Chatwoot Processor (Optional Sub-Agent)

**Goal:** If database queries needed, wrap `query_database` as imported tool.

- [ ] Import existing tools from other experts:
  ```python
  # In purchase_tools.py
  from juan.database_expert.database_tools import query_database
  
  def get_purchase_tools():
      return [
          create_purchase_quote,
          confirm_purchase_order,
          check_order_status,
          query_database,  # Agent-as-tool pattern
      ]
  ```
- [ ] **Do NOT create custom graph** — import pre-existing tools only
- [ ] Test agent can invoke `query_database` for provider lookups
- [ ] Commit: `feat(phase3): integrate database_expert tool`

---

## 📋 Task Group 3.1.5 — Testing Following Existing Patterns

**Goal:** Unit tests for tools and agent invocation.

- [ ] Create `tests/purchase_expert/test_purchase_tools.py`:
  - Mock `odoo_manager.get_purchase_client()`
  - Test each tool with valid/invalid inputs
  - Verify error handling
- [ ] Create `tests/purchase_expert/test_purchase_agent.py`:
  - Test agent invocation with sample messages
  - Verify `PurchaseResponseModel` serialization
  - Test tool selection logic
- [ ] Create `tests/purchase_expert/test_integration.py`:
  - E2E flow: create RFQ → confirm → check status
  - Use real Odoo staging environment (optional)
- [ ] All tests pass: `poetry run pytest tests/purchase_expert -v`
- [ ] Commit: `test(phase3): add purchase expert test suite`

---

## ✅ Completion Criteria

- [ ] Models follow `production_models.py` structure (BaseModel + Field descriptions)
- [ ] Tools use `@tool` decorator with lazy initialization pattern
- [ ] Agent built with `create_react_agent` (NO custom StateGraph)
- [ ] Imports tools from other experts using agent-as-tool pattern
- [ ] Test coverage ≥80% for tools and agent invocation
- [ ] All tests passing in CI
- [ ] Code matches existing architectural patterns

---

## 🎯 Architecture Compliance Checklist

- [ ] ❌ NO custom `StateGraph` definitions
- [ ] ❌ NO manual node/edge configuration
- [ ] ✅ Uses `langgraph.prebuilt.create_react_agent`
- [ ] ✅ Response format via Pydantic `response_format=`
- [ ] ✅ Tools imported from other experts (agent-as-tool)
- [ ] ✅ Lazy initialization for API clients
- [ ] ✅ Follows `production_expert` file structure

---

## 📅 Timeline & Dependencies

**Estimated effort:** 3-4 business days  
**Blockers:** Access to Odoo staging/production instance  
**Dependencies:**  
- `odoo_manager` library with purchase.order support  
- Existing `juan.config.get_llm` infrastructure  
- `langchain_core` and `langgraph.prebuilt`

---

## 🚀 Next Actions

1. ✅ Review `production_expert` implementation thoroughly
2. Create `purchase_models.py` mirroring `production_models.py`
3. Implement tools with lazy initialization pattern
4. Build agent using `create_react_agent` only
5. Write tests following existing patterns

---

## Legacy Phase 3 Checklist (archived for reference)

# 🧭 **Phase 3 Implementation Checklist — Purchase Order Handler Agent**

**Project:** Chatwoot Processor → LangGraph Multi-Agent Integration  
**Phase:** 3 — Purchase Order Handler Agent  
**Status:** 🔜 Ready to Start  
**Prerequisites:** ✅ Phase 1-2 Complete  

---

## 📋 **Phase 3.1 — Protocols & Adapters Foundation**

**Goal:** Define clear interfaces for Odoo interaction and Postgres I/O.

## 📋 **Phase 3.2 — create_react_agent Assembly & Tool Exposure**

**Goal:** Instantiate the purchase expert via LangGraph's prebuilt `create_react_agent`, expose it with the agent-as-a-tool pattern, and stay aligned with the production expert without introducing custom graphs.

### **Task 3.2.1 — Purchase Tool Catalogue**

- [ ] Keep `src/juan/purchase_expert/purchase_tools.py` aligned with the service layer and export `get_purchase_tools()`.
- [ ] Ensure each tool returns JSON-serializable payloads suitable for `create_react_agent` structured responses.
- [ ] Add type hints and docstrings mirroring the production expert conventions.
- [ ] Commit: `feat(phase3): curate purchase expert tools`.

---

### **Task 3.2.2 — Instantiate `purchase_agent` with `create_react_agent`**

- [ ] Create `src/juan/purchase_expert/purchase_agent.py` by following `production_expert/production_agent.py`.
- [ ] Use `create_react_agent` from `langgraph.prebuilt` plus `MemorySaver` for checkpointing.
- [ ] Wire `get_llm`, `get_purchase_tools()`, and `PurchaseResponseModel` into the instantiation.
- [ ] Export the compiled agent through `__all__` and surface it via `purchase_expert/__init__.py`.
- [ ] Commit: `feat(phase3): add purchase_agent prebuilt instance`.

---

### **Task 3.2.3 — Publish the agent via agent-as-a-tool**

- [ ] Provide `get_purchase_agent_tool()` (or equivalent helper) that wraps the compiled agent using its built-in `.as_tool()` / tool interface so other agents can invoke it.
- [ ] Document invocation semantics (e.g., `.invoke`, `.stream`) and configuration parameters such as `thread_id` and recursion limits.
- [ ] Mirror existing multi-agent orchestrations so schedulers can plug the purchase expert in as a regular tool.
- [ ] Commit: `feat(phase3): expose purchase agent tool`.

---

### **Task 3.2.4 — Registration & configuration**

- [ ] Update `langgraph.json` to register the purchase agent entrypoint—no custom graphs should be introduced.
- [ ] Extend orchestrators (Slack/console controllers, schedulers) to import the new agent tool and add it to coordination lists.
- [ ] Verify `src/juan/purchase_expert/__init__.py` surfaces both `purchase_agent` and `get_purchase_agent_tool()`.
- [ ] Commit: `chore(phase3): register purchase agent`.

---

### **Task 3.2.5 — Smoke tests & CI integration**

- [ ] Add `tests/purchase_agent/test_agent_entrypoint.py` ensuring `purchase_agent` loads with `create_react_agent` and returns `PurchaseResponseModel` payloads.
- [ ] Add tests confirming the agent-as-a-tool wrapper delegates correctly and preserves structured responses.
- [ ] Guard against accidental imports of `StateGraph` / custom graph APIs (lint rule or unit test assertion).
- [ ] Commit: `test(phase3): cover purchase agent bootstrap`.

---
      adapter = get_postgres_io_adapter()
      messages = await adapter.fetch_pending_messages(...)
      return [msg.to_dict() for msg in messages]
  ```
- [ ] Implement `send_reply` tool:
  ```python
  @tool
  async def send_reply(
      conversation_id: int,
      content: str
  ) -> dict:
      """Queue outbound message for provider."""
      adapter = get_postgres_io_adapter()
      message = await adapter.queue_outbound_message(...)
      return message.to_dict()
  ```
- [ ] Implement `create_purchase_quote` tool:
  ```python
  @tool
  async def create_purchase_quote(
      provider_id: str,
      items: list[dict],
      expected_date: str | None = None
  ) -> dict:
      """Create RFQ in Odoo."""
      adapter = get_odoo_adapter()
      order_id = await adapter.create_rfq(...)
      return {"order_id": order_id, "status": "draft"}
  ```
- [ ] Implement `confirm_purchase_order` tool:
  ```python
  @tool
  async def confirm_purchase_order(order_id: str) -> dict:
      """Confirm purchase order in Odoo."""
      adapter = get_odoo_adapter()
      success = await adapter.confirm_order(order_id)
      return {"order_id": order_id, "confirmed": success}
  ```
- [ ] Implement `check_order_status` tool:
  ```python
  @tool
  async def check_order_status(order_id: str) -> dict:
      """Get order status from Odoo."""
      adapter = get_odoo_adapter()
      status = await adapter.get_order_status(order_id)
      return status.to_dict()
  ```
- [ ] Commit: `feat(phase3): implement LangGraph tools`

---

### **Task 3.2.2 — Define Agent State**

- [ ] Create `src/purchase_agent/state.py`
- [ ] Define `PurchaseAgentState`:
  ```python
  class PurchaseAgentState(TypedDict):
      # Input
      user_identifier: str
      channel: str
      
      # Processing
      messages: list[MessageRecord]
      current_message: MessageRecord | None
      intent: str | None  # "create_rfq" | "confirm" | "status" | "cancel"
      
      # Order context
      active_order_id: str | None
      order_items: list[OrderItem]
      
      # Output
      reply_content: str | None
      action_taken: str | None
      error: str | None
  ```
- [ ] Add helper methods:
  - `add_message(message: MessageRecord)`
  - `set_intent(intent: str)`
  - `set_active_order(order_id: str)`
- [ ] Commit: `feat(phase3): define PurchaseAgentState`

---

### **Task 3.2.3 — Implement Agent Graph Nodes**

- [ ] Create `src/purchase_agent/graph/nodes.py`
- [ ] Implement `message_reader` node:
  ```python
  async def message_reader(state: PurchaseAgentState) -> PurchaseAgentState:
      """Read pending messages from Postgres."""
      messages = await fetch_pending_messages(
          user_identifier=state["user_identifier"],
          channel=state["channel"]
      )
      state["messages"] = messages
      state["current_message"] = messages[0] if messages else None
      return state
  ```
- [ ] Implement `intent_classifier` node:
  ```python
  async def intent_classifier(state: PurchaseAgentState) -> PurchaseAgentState:
      """Classify user intent from message."""
      message = state["current_message"]
      # Use LLM to classify intent
      intent = await classify_intent(message.content)
      state["intent"] = intent
      return state
  ```
- [ ] Implement `order_handler` node:
  ```python
  async def order_handler(state: PurchaseAgentState) -> PurchaseAgentState:
      """Execute order action based on intent."""
      intent = state["intent"]
      if intent == "create_rfq":
          result = await create_purchase_quote(...)
          state["active_order_id"] = result["order_id"]
      elif intent == "confirm":
          result = await confirm_purchase_order(state["active_order_id"])
      # ... other intents
      state["action_taken"] = intent
      return state
  ```
- [ ] Implement `response_generator` node:
  ```python
  async def response_generator(state: PurchaseAgentState) -> PurchaseAgentState:
      """Generate reply to provider."""
      # Use LLM to generate natural response
      reply = await generate_response(
          intent=state["intent"],
          action=state["action_taken"],
          order_id=state.get("active_order_id")
      )
      state["reply_content"] = reply
      return state
  ```
- [ ] Implement `message_dispatcher` node:
  ```python
  async def message_dispatcher(state: PurchaseAgentState) -> PurchaseAgentState:
      """Queue outbound message."""
      conversation = await get_active_conversation(
          user_identifier=state["user_identifier"],
          channel=state["channel"]
      )
      await send_reply(
          conversation_id=conversation.id,
          content=state["reply_content"]
      )
      return state
  ```
- [ ] Commit: `feat(phase3): implement agent graph nodes`

---

### **Task 3.2.4 — Build Agent Graph**

- [ ] Create `src/purchase_agent/graph/graph.py`
- [ ] Implement graph builder:
  ```python
  from langgraph.graph import StateGraph, END
  
  def build_purchase_agent_graph() -> StateGraph:
      workflow = StateGraph(PurchaseAgentState)
      
      # Add nodes
      workflow.add_node("read_messages", message_reader)
      workflow.add_node("classify_intent", intent_classifier)
      workflow.add_node("handle_order", order_handler)
      workflow.add_node("generate_response", response_generator)
      workflow.add_node("dispatch_message", message_dispatcher)
      
      # Define edges
      workflow.set_entry_point("read_messages")
      workflow.add_edge("read_messages", "classify_intent")
      workflow.add_edge("classify_intent", "handle_order")
      workflow.add_edge("handle_order", "generate_response")
      workflow.add_edge("generate_response", "dispatch_message")
      workflow.add_edge("dispatch_message", END)
      
      return workflow.compile()
  ```
- [ ] Add conditional routing (optional):
  ```python
  def should_handle_order(state: PurchaseAgentState) -> str:
      if state["intent"] in ["create_rfq", "confirm", "cancel"]:
          return "handle_order"
      else:
          return "generate_response"
  
  workflow.add_conditional_edges(
      "classify_intent",
      should_handle_order
  )
  ```
- [ ] Commit: `feat(phase3): build purchase agent graph`

---

### **Task 3.2.5 — Agent Entrypoint & Configuration**

- [ ] Create `src/purchase_agent/main.py`
- [ ] Implement agent entrypoint:
  ```python
  async def run_purchase_agent(
      user_identifier: str,
      channel: str = "whatsapp"
  ) -> dict:
      """Run purchase agent for given provider."""
      graph = build_purchase_agent_graph()
      
      initial_state: PurchaseAgentState = {
          "user_identifier": user_identifier,
          "channel": channel,
          "messages": [],
          "current_message": None,
          "intent": None,
          "active_order_id": None,
          "order_items": [],
          "reply_content": None,
          "action_taken": None,
          "error": None,
      }
      
      result = await graph.ainvoke(initial_state)
      return result
  ```
- [ ] Update `langgraph.json`:
  ```json
  {
    "agents": [
      {
        "name": "purchase-order-handler",
        "module": "src.purchase_agent.main",
        "function": "run_purchase_agent",
        "description": "Handles purchase order negotiation with providers",
        "tools": [
          "fetch_pending_messages",
          "send_reply",
          "create_purchase_quote",
          "confirm_purchase_order",
          "check_order_status"
        ]
      }
    ]
  }
  ```
- [ ] Commit: `feat(phase3): add agent entrypoint and LangGraph config`

---

### **Task 3.2.6 — Basic Agent Tests**

- [ ] Create `tests/purchase_agent/test_tools.py`:
  - [ ] `test_fetch_pending_messages_tool`
  - [ ] `test_send_reply_tool`
  - [ ] `test_create_purchase_quote_tool`
  - [ ] `test_confirm_purchase_order_tool`
  - [ ] `test_check_order_status_tool`
- [ ] Create `tests/purchase_agent/test_graph.py`:
  - [ ] `test_graph_nodes_connected_correctly`
  - [ ] `test_message_reader_fetches_messages`
  - [ ] `test_intent_classifier_classifies_correctly`
  - [ ] `test_order_handler_creates_rfq`
  - [ ] `test_response_generator_creates_reply`
  - [ ] `test_message_dispatcher_queues_message`
- [ ] Create `tests/purchase_agent/test_agent_flow.py`:
  - [ ] `test_agent_handles_new_rfq_request`
  - [ ] `test_agent_confirms_existing_order`
  - [ ] `test_agent_checks_order_status`
- [ ] All tests use mock adapters
- [ ] Commit: `test(phase3): add agent graph and tool tests`

---

### **Phase 3.2 Completion Criteria:**

- [ ] All LangGraph tools implemented
- [ ] Agent state defined with proper types
- [ ] All graph nodes implemented
- [ ] Graph properly connected with edges
- [ ] Agent entrypoint functional
- [ ] langgraph.json updated
- [ ] ≥85% test coverage for tools and graph
- [ ] All tests passing
- [ ] Documentation updated

**Estimated Duration:** 5-7 días  
**Blockers:** LangGraph library version compatibility  
**Dependencies:** Phase 3.1 complete

---

## 📋 **Phase 3.3 — Business Logic & Workflow**

**Goal:** Implement domain-specific business logic for purchase order management.

### **Task 3.3.1 — Intent Classification**

- [ ] Create `src/purchase_agent/intent_classifier.py`
- [ ] Define intent prompts:
  ```python
  INTENT_CLASSIFICATION_PROMPT = """
  Classify the provider's message intent into one of:
  - "create_rfq": Request new quotation
  - "confirm_order": Confirm existing order
  - "check_status": Query order status
  - "modify_order": Modify existing order
  - "cancel_order": Cancel order
  - "general_inquiry": General question
  
  Message: {message_content}
  
  Return only the intent code.
  """
  ```
- [ ] Implement LLM-based classifier:
  ```python
  async def classify_intent(message_content: str) -> str:
      llm = get_llm()  # from config
      response = await llm.ainvoke(
          INTENT_CLASSIFICATION_PROMPT.format(
              message_content=message_content
          )
      )
      return response.strip().lower()
  ```
- [ ] Add fallback to keyword matching if LLM fails
- [ ] Add confidence scoring
- [ ] Commit: `feat(phase3): implement intent classification`

---

### **Task 3.3.2 — Order State Machine**

- [ ] Create `src/purchase_agent/order_state_machine.py`
- [ ] Define state transitions:
  ```python
  class OrderState(StrEnum):
      DRAFT = "draft"
      SENT = "sent"
      CONFIRMED = "confirmed"
      RECEIVED = "received"
      BILLED = "billed"
      CANCELLED = "cancelled"
  
  ALLOWED_TRANSITIONS: dict[OrderState, set[OrderState]] = {
      OrderState.DRAFT: {OrderState.SENT, OrderState.CANCELLED},
      OrderState.SENT: {OrderState.CONFIRMED, OrderState.CANCELLED},
      OrderState.CONFIRMED: {OrderState.RECEIVED, OrderState.CANCELLED},
      OrderState.RECEIVED: {OrderState.BILLED},
      OrderState.BILLED: set(),
      OrderState.CANCELLED: set(),
  }
  ```
- [ ] Implement transition validator:
  ```python
  def can_transition(
      current: OrderState,
      target: OrderState
  ) -> bool:
      return target in ALLOWED_TRANSITIONS.get(current, set())
  
  def validate_transition(
      current: OrderState,
      target: OrderState
  ) -> None:
      if not can_transition(current, target):
          raise InvalidOrderTransition(
              f"Cannot transition from {current} to {target}"
          )
  ```
- [ ] Add state machine tests
- [ ] Commit: `feat(phase3): implement order state machine`

---

### **Task 3.3.3 — Validation Rules**

- [ ] Create `src/purchase_agent/validators.py`
- [ ] Implement "one active order per provider" rule:
  ```python
  async def ensure_no_active_order(
      provider_id: str,
      session: AsyncSession
  ) -> None:
      """Verify provider has no active orders."""
      # Query for active orders (state != received/billed/cancelled)
      active_orders = await get_active_orders(provider_id, session)
      if active_orders:
          raise ActiveOrderExists(
              f"Provider {provider_id} has {len(active_orders)} active order(s)"
          )
  ```
- [ ] Implement inventory validation:
  ```python
  async def validate_inventory_availability(
      items: list[OrderItem]
  ) -> dict[str, bool]:
      """Check if products are available for ordering."""
      # Query Odoo for product availability
      ...
  ```
- [ ] Implement price validation:
  ```python
  async def validate_price_against_history(
      provider_id: str,
      items: list[OrderItem]
  ) -> dict[str, PriceCheck]:
      """Compare prices against historical average."""
      # Query price history
      # Flag items with >20% deviation
      ...
  ```
- [ ] Implement minimum order value:
  ```python
  def validate_minimum_order_value(
      items: list[OrderItem],
      min_value: Decimal = Decimal("100.00")
  ) -> None:
      total = sum(item.quantity * item.unit_price for item in items)
      if total < min_value:
          raise OrderBelowMinimum(f"Order total {total} below minimum {min_value}")
  ```
- [ ] Commit: `feat(phase3): implement validation rules`

---

### **Task 3.3.4 — Error Handling & Recovery**

- [ ] Create `src/purchase_agent/error_handlers.py`
- [ ] Define custom exceptions:
  ```python
  class PurchaseAgentError(Exception):
      """Base exception for purchase agent."""
  
  class OdooAPIError(PurchaseAgentError):
      """Odoo API call failed."""
  
  class InvalidOrderState(PurchaseAgentError):
      """Order in invalid state for operation."""
  
  class ActiveOrderExists(PurchaseAgentError):
      """Provider has active order."""
  
  class ValidationError(PurchaseAgentError):
      """Order validation failed."""
  ```
- [ ] Implement error recovery strategies:
  ```python
  async def handle_odoo_failure(
      error: OdooAPIError,
      operation: str,
      retry_count: int = 0
  ) -> bool:
      """Handle Odoo API failures with retry."""
      if retry_count < 3:
          await asyncio.sleep(2 ** retry_count)  # exponential backoff
          return True  # retry
      else:
          # Send error notification to Slack
          await notify_slack(f"Odoo operation {operation} failed permanently")
          return False  # give up
  ```
- [ ] Add circuit breaker for Odoo:
  ```python
  class OdooCircuitBreaker:
      def __init__(self, failure_threshold: int = 5):
          self._failures = 0
          self._threshold = failure_threshold
          self._open_until: datetime | None = None
      
      def is_open(self) -> bool:
          if self._open_until and datetime.now() < self._open_until:
              return True
          return False
      
      def record_failure(self) -> None:
          self._failures += 1
          if self._failures >= self._threshold:
              self._open_until = datetime.now() + timedelta(minutes=5)
      
      def record_success(self) -> None:
          self._failures = 0
          self._open_until = None
  ```
- [ ] Commit: `feat(phase3): implement error handling and recovery`

---

### **Task 3.3.5 — Workflow Orchestration**

- [ ] Create `src/purchase_agent/workflows/__init__.py`
- [ ] Implement "Create RFQ" workflow:
  ```python
  async def workflow_create_rfq(
      provider_id: str,
      items: list[OrderItem],
      session: AsyncSession
  ) -> str:
      # 1. Validate no active orders
      await ensure_no_active_order(provider_id, session)
      
      # 2. Validate inventory
      availability = await validate_inventory_availability(items)
      
      # 3. Validate minimum order value
      validate_minimum_order_value(items)
      
      # 4. Create RFQ in Odoo
      odoo = get_odoo_adapter()
      order_id = await odoo.create_rfq(provider_id, items)
      
      # 5. Store order reference in conversation state
      await store_order_context(provider_id, order_id, session)
      
      return order_id
  ```
- [ ] Implement "Confirm Order" workflow:
  ```python
  async def workflow_confirm_order(
      provider_id: str,
      session: AsyncSession
  ) -> bool:
      # 1. Get active order for provider
      order_id = await get_active_order_id(provider_id, session)
      
      # 2. Validate price one more time
      # ...
      
      # 3. Confirm in Odoo
      odoo = get_odoo_adapter()
      success = await odoo.confirm_order(order_id)
      
      # 4. Update conversation state
      await update_order_state(order_id, OrderState.CONFIRMED, session)
      
      return success
  ```
- [ ] Implement "Check Status" workflow
- [ ] Implement "Modify Order" workflow
- [ ] Implement "Cancel Order" workflow
- [ ] Add transaction boundaries
- [ ] Commit: `feat(phase3): implement order workflows`

---

### **Task 3.3.6 — Response Generation**

- [ ] Create `src/purchase_agent/response_generator.py`
- [ ] Define response templates:
  ```python
  RESPONSE_TEMPLATES = {
      "rfq_created": """
      Cotización #{order_id} creada exitosamente.
      
      Productos:
      {items_list}
      
      Total: ${total}
      
      ¿Deseas confirmar esta orden?
      """,
      
      "order_confirmed": """
      Orden #{order_id} confirmada.
      
      Fecha estimada de entrega: {expected_date}
      
      Te notificaremos cuando esté lista.
      """,
      
      "order_status": """
      Estado de orden #{order_id}: {status}
      
      {status_details}
      """,
  }
  ```
- [ ] Implement LLM-enhanced generation:
  ```python
  async def generate_response(
      template_key: str,
      context: dict,
      personalize: bool = True
  ) -> str:
      base_response = RESPONSE_TEMPLATES[template_key].format(**context)
      
      if personalize:
          llm = get_llm()
          personalized = await llm.ainvoke(
              f"Make this response more natural and friendly:\n{base_response}"
          )
          return personalized
      
      return base_response
  ```
- [ ] Add multi-language support (ES/EN)
- [ ] Commit: `feat(phase3): implement response generation`

---

### **Phase 3.3 Completion Criteria:**

- [ ] Intent classification with LLM + fallback
- [ ] Order state machine with validated transitions
- [ ] All validation rules implemented
- [ ] Error handling with retry + circuit breaker
- [ ] All workflows implemented
- [ ] Response generation with templates + LLM
- [ ] ≥80% test coverage for business logic
- [ ] All tests passing
- [ ] Documentation updated

**Estimated Duration:** 5-7 días  
**Blockers:** None  
**Dependencies:** Phase 3.2 complete

---

## 📋 **Phase 3.4 — Integration & Testing**

**Goal:** Integrate agent with Chatwoot Processor and comprehensive E2E testing.

### **Task 3.4.1 — Shared Database Integration**

- [ ] Verify database schema compatibility
- [ ] Create migration for order tracking table (optional):
  ```sql
  CREATE TABLE IF NOT EXISTS communication.order_context (
      id SERIAL PRIMARY KEY,
      conversation_id INTEGER REFERENCES communication.conversation(id),
      order_id VARCHAR(255) NOT NULL,
      order_state VARCHAR(50) NOT NULL,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
      updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
  );
  ```
- [ ] Update Alembic migration:
  ```bash
  cd /Users/bastianibanez/work/libraries/chatwoot-processor
  alembic revision -m "add_order_context_table"
  ```
- [ ] Test migration on SQLite and Postgres
- [ ] Commit: `feat(phase3): add order context tracking table`

---

### **Task 3.4.2 — Message Status Synchronization**

- [ ] Implement status sync service:
  ```python
  class MessageStatusSync:
      async def mark_messages_processed(
          self,
          message_ids: list[int],
          session: AsyncSession
      ) -> None:
          """Mark messages as read after agent processing."""
          from src.services.conversation_service import update_message_status
          for msg_id in message_ids:
              await update_message_status(
                  session,
                  msg_id,
                  MessageStatus.READ
              )
  ```
- [ ] Integrate into agent graph:
  ```python
  # In message_dispatcher node:
  async def message_dispatcher(state: PurchaseAgentState):
      # ... queue outbound message ...
      
      # Mark inbound messages as read
      message_ids = [msg.id for msg in state["messages"]]
      sync = MessageStatusSync()
      await sync.mark_messages_processed(message_ids, session)
      
      return state
  ```
- [ ] Add tests for synchronization
- [ ] Commit: `feat(phase3): implement message status sync`

---

### **Task 3.4.3 — Conversation State Coordination**

- [ ] Implement conversation context manager:
  ```python
  class ConversationContextManager:
      async def get_order_context(
          self,
          conversation_id: int,
          session: AsyncSession
      ) -> OrderContext | None:
          """Get active order for conversation."""
          ...
      
      async def set_order_context(
          self,
          conversation_id: int,
          order_id: str,
          session: AsyncSession
      ) -> None:
          """Store order reference for conversation."""
          ...
      
      async def clear_order_context(
          self,
          conversation_id: int,
          session: AsyncSession
      ) -> None:
          """Clear order reference when complete."""
          ...
  ```
- [ ] Integrate into workflows
- [ ] Add tests
- [ ] Commit: `feat(phase3): implement conversation context management`

---

### **Task 3.4.4 — E2E Test Suite**

- [ ] Create `tests/purchase_agent/integration/test_order_creation.py`:
  ```python
  @pytest.mark.asyncio
  async def test_create_rfq_from_whatsapp_message(
      async_client,
      session_factory,
      conversation_factory
  ):
      # 1. Create conversation
      conv = await conversation_factory("+5491234567", "whatsapp")
      
      # 2. Send webhook with RFQ request
      payload = {
          "channel_type": "whatsapp",
          "contact": {"phone_number": "+5491234567"},
          "content": "Necesito cotización para 100kg aceite de coco"
      }
      response = await async_client.post("/webhook/chatwoot", json=payload)
      assert response.status_code == 200
      
      # 3. Run purchase agent
      result = await run_purchase_agent("+5491234567", "whatsapp")
      
      # 4. Verify order created
      assert result["action_taken"] == "create_rfq"
      assert result["active_order_id"] is not None
      
      # 5. Verify outbound message queued
      async with session_factory() as session:
          messages = await session.execute(
              select(MessageRecord)
              .where(
                  MessageRecord.conversation_id == conv.id,
                  MessageRecord.direction == MessageDirection.OUTBOUND,
                  MessageRecord.status == MessageStatus.QUEUED
              )
          )
          outbound = messages.scalars().first()
          assert outbound is not None
          assert "cotización" in outbound.content.lower()
  ```

- [ ] Create `tests/purchase_agent/integration/test_order_confirmation.py`:
  - [ ] `test_confirm_order_from_provider_reply`
  - [ ] `test_reject_confirmation_without_active_order`
  - [ ] `test_confirmation_updates_order_state`

- [ ] Create `tests/purchase_agent/integration/test_concurrent_orders.py`:
  - [ ] `test_prevent_duplicate_orders_same_provider`
  - [ ] `test_multiple_providers_concurrent_orders`
  - [ ] `test_locking_prevents_race_condition`

- [ ] Create `tests/purchase_agent/integration/test_odoo_failures.py`:
  - [ ] `test_retry_on_odoo_connection_error`
  - [ ] `test_circuit_breaker_opens_after_failures`
  - [ ] `test_fallback_message_on_permanent_failure`

- [ ] Commit: `test(phase3): add comprehensive E2E integration tests`

---

### **Task 3.4.5 — End-to-End Simulation**

- [ ] Create `tests/purchase_agent/simulation/test_full_negotiation.py`:
  ```python
  @pytest.mark.asyncio
  @pytest.mark.slow
  async def test_full_purchase_negotiation_flow(
      async_client,
      session_factory,
      mock_chatwoot_adapter
  ):
      """
      Simulate full negotiation:
      Provider → Chatwoot → Processor → Agent → Odoo → Agent → Processor → Chatwoot
      """
      # 1. Provider sends initial request (WhatsApp)
      await send_webhook({
          "channel_type": "whatsapp",
          "contact": {"phone_number": "+5491111111"},
          "content": "Hola, necesito 50kg de aceite de coco"
      })
      
      # 2. Agent processes and creates RFQ
      result = await run_purchase_agent("+5491111111", "whatsapp")
      order_id = result["active_order_id"]
      
      # 3. Verify outbound message sent to Chatwoot
      assert mock_chatwoot_adapter.sent_messages[-1]["content"].startswith("Cotización")
      
      # 4. Provider confirms order
      await send_webhook({
          "channel_type": "whatsapp",
          "contact": {"phone_number": "+5491111111"},
          "content": "Sí, confirmar orden"
      })
      
      # 5. Agent processes and confirms in Odoo
      result = await run_purchase_agent("+5491111111", "whatsapp")
      assert result["action_taken"] == "confirm_order"
      
      # 6. Verify order confirmed in Odoo
      odoo = get_odoo_adapter()
      status = await odoo.get_order_status(order_id)
      assert status.state == OrderState.CONFIRMED
      
      # 7. Verify confirmation message sent
      assert "confirmada" in mock_chatwoot_adapter.sent_messages[-1]["content"].lower()
  ```
- [ ] Add timing assertions (performance)
- [ ] Add logging for debugging
- [ ] Commit: `test(phase3): add full negotiation simulation`

---

### **Task 3.4.6 — Mock vs Real Testing Strategy**

- [ ] Document testing modes in README:
  ```markdown
  ## Testing Modes
  
  ### Mock Mode (Default)
  ```bash
  export ODOO_ADAPTER=mock
  pytest tests/purchase_agent/
  ```
  
  ### Staging Mode
  ```bash
  export ODOO_ADAPTER=staging
  export ODOO_STAGING_URL=...
  pytest tests/purchase_agent/integration/
  ```
  
  ### Production Dry-Run
  ```bash
  export ODOO_ADAPTER=production
  export DRY_RUN=true
  pytest tests/purchase_agent/integration/test_order_creation.py
  ```
  ```
- [ ] Implement adapter selection in tests:
  ```python
  @pytest.fixture
  def odoo_adapter():
      mode = os.getenv("ODOO_ADAPTER", "mock")
      return get_odoo_adapter(mode)
  ```
- [ ] Add `@pytest.mark.requires_staging` decorator
- [ ] Add `@pytest.mark.requires_production` decorator
- [ ] Update CI/CD to use mock by default
- [ ] Commit: `test(phase3): implement mock vs real testing strategy`

---

### **Phase 3.4 Completion Criteria:**

- [ ] Shared database integration working
- [ ] Message status synchronized between processor and agent
- [ ] Conversation context properly managed
- [ ] Full E2E test suite (≥15 tests)
- [ ] Full negotiation flow simulation passing
- [ ] Mock and real testing modes documented
- [ ] ≥85% overall test coverage
- [ ] All tests passing in mock mode
- [ ] Staging tests passing (optional)
- [ ] Performance benchmarks documented

**Estimated Duration:** 7-10 días  
**Blockers:** Access to staging Odoo instance  
**Dependencies:** Phase 3.3 complete

---

## 📋 **Phase 3.5 — Monitoring & Deployment**

**Goal:** Production readiness with monitoring, deployment, and documentation.

### **Task 3.5.1 — Structured Logging**

- [ ] Create `src/purchase_agent/logging_config.py`
- [ ] Implement JSON structured logging:
  ```python
  import structlog
  
  structlog.configure(
      processors=[
          structlog.stdlib.filter_by_level,
          structlog.stdlib.add_logger_name,
          structlog.stdlib.add_log_level,
          structlog.stdlib.PositionalArgumentsFormatter(),
          structlog.processors.TimeStamper(fmt="iso"),
          structlog.processors.StackInfoRenderer(),
          structlog.processors.format_exc_info,
          structlog.processors.UnicodeDecoder(),
          structlog.processors.JSONRenderer()
      ],
      context_class=dict,
      logger_factory=structlog.stdlib.LoggerFactory(),
      cache_logger_on_first_use=True,
  )
  ```
- [ ] Add logging to critical paths:
  ```python
  logger = structlog.get_logger()
  
  # In workflows:
  logger.info(
      "rfq_created",
      provider_id=provider_id,
      order_id=order_id,
      items_count=len(items),
      total_value=total
  )
  
  logger.error(
      "odoo_api_failure",
      operation="create_rfq",
      provider_id=provider_id,
      error=str(error),
      retry_count=retry_count
  )
  ```
- [ ] Add request tracing (correlation IDs)
- [ ] Commit: `feat(phase3): implement structured logging`

---

### **Task 3.5.2 — Order Lifecycle Tracking**

- [ ] Create `src/purchase_agent/metrics.py`
- [ ] Implement order metrics:
  ```python
  from prometheus_client import Counter, Histogram, Gauge
  
  orders_created = Counter(
      "purchase_orders_created_total",
      "Total purchase orders created",
      ["provider_id"]
  )
  
  orders_confirmed = Counter(
      "purchase_orders_confirmed_total",
      "Total purchase orders confirmed"
  )
  
  order_processing_duration = Histogram(
      "purchase_order_processing_seconds",
      "Time to process purchase order",
      ["operation"]
  )
  
  active_orders = Gauge(
      "purchase_orders_active",
      "Currently active purchase orders"
  )
  ```
- [ ] Add metrics to workflows:
  ```python
  # In workflow_create_rfq:
  with order_processing_duration.labels(operation="create_rfq").time():
      order_id = await odoo.create_rfq(...)
  
  orders_created.labels(provider_id=provider_id).inc()
  active_orders.inc()
  ```
- [ ] Add `/metrics` endpoint to FastAPI
- [ ] Commit: `feat(phase3): add Prometheus metrics`

---

### **Task 3.5.3 — Error Rate Monitoring**

- [ ] Implement error tracking:
  ```python
  error_counter = Counter(
      "purchase_agent_errors_total",
      "Total errors in purchase agent",
      ["error_type", "operation"]
  )
  
  # In error handlers:
  error_counter.labels(
      error_type=type(error).__name__,
      operation=operation
  ).inc()
  ```
- [ ] Add Slack notifications for critical errors:
  ```python
  async def notify_critical_error(
      error: Exception,
      context: dict
  ) -> None:
      if os.getenv("ENV") == "production":
          slack = get_slack_client()
          await slack.send_message(
              channel="#purchase-agent-alerts",
              text=f"🚨 Critical Error: {error}\nContext: {context}"
          )
  ```
- [ ] Add error rate alerts (threshold-based)
- [ ] Commit: `feat(phase3): implement error monitoring and alerts`

---

### **Task 3.5.4 — Configuration Management**

- [ ] Update `config/config_vars.yaml`:
  ```yaml
  # Purchase Agent Config
  PURCHASE_AGENT_ENV:
    env_var: PURCHASE_AGENT_ENV
    default: "development"
  
  PURCHASE_AGENT_LLM_MODEL:
    env_var: PURCHASE_AGENT_LLM_MODEL
    default: "gpt-4o-mini"
  
  PURCHASE_AGENT_MAX_RETRIES:
    env_var: PURCHASE_AGENT_MAX_RETRIES
    default: "3"
  
  PURCHASE_AGENT_CIRCUIT_BREAKER_THRESHOLD:
    env_var: PURCHASE_AGENT_CIRCUIT_BREAKER_THRESHOLD
    default: "5"
  
  # Odoo Config
  ODOO_URL:
    env_var: PURCHASE_AGENT_ODOO_URL
    secret: false
  
  ODOO_DB:
    env_var: PURCHASE_AGENT_ODOO_DB
    secret: false
  
  ODOO_USERNAME:
    env_var: PURCHASE_AGENT_ODOO_USERNAME
    secret: true
  
  ODOO_PASSWORD:
    env_var: PURCHASE_AGENT_ODOO_PASSWORD
    secret: true
  ```
- [ ] Add environment-specific configs:
  - [ ] `config/development.yaml`
  - [ ] `config/staging.yaml`
  - [ ] `config/production.yaml`
- [ ] Implement config loader:
  ```python
  def load_config() -> dict:
      env = os.getenv("PURCHASE_AGENT_ENV", "development")
      base_config = load_yaml("config/config_vars.yaml")
      env_config = load_yaml(f"config/{env}.yaml")
      return {**base_config, **env_config}
  ```
- [ ] Add feature flags:
  ```python
  FEATURE_FLAGS = {
      "enable_price_validation": True,
      "enable_inventory_check": False,
      "enable_llm_personalization": True,
  }
  ```
- [ ] Commit: `feat(phase3): implement environment-based configuration`

---

### **Task 3.5.5 — Deployment Configuration**

- [ ] Update `deployment/Dockerfile`:
  ```dockerfile
  # Add purchase agent dependencies
  RUN poetry install --only main --no-root
  
  # Copy purchase agent code
  COPY src/purchase_agent /app/src/purchase_agent
  
  # Expose metrics port (optional)
  EXPOSE 8001
  ```
- [ ] Update `deployment/docker-compose.prod.yaml`:
  ```yaml
  services:
    chatwoot-processor:
      # ... existing config ...
      environment:
        - PURCHASE_AGENT_ENV=production
        - PURCHASE_AGENT_ODOO_URL=${ODOO_URL}
        - PURCHASE_AGENT_ODOO_DB=${ODOO_DB}
        - PURCHASE_AGENT_ODOO_USERNAME=${ODOO_USERNAME}
        - PURCHASE_AGENT_ODOO_PASSWORD=${ODOO_PASSWORD}
      healthcheck:
        test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
        interval: 30s
        timeout: 10s
        retries: 3
    
    purchase-agent-scheduler:
      build:
        context: .
        dockerfile: deployment/Dockerfile
      command: python -m src.purchase_agent.scheduler
      environment:
        - PURCHASE_AGENT_ENV=production
        - DATABASE_URL=${DATABASE_URL}
      depends_on:
        - postgres
      restart: unless-stopped
  ```
- [ ] Create scheduler for periodic agent runs:
  ```python
  # src/purchase_agent/scheduler.py
  import asyncio
  from apscheduler.schedulers.asyncio import AsyncIOScheduler
  
  async def run_agent_for_all_conversations():
      # Get all conversations with pending messages
      conversations = await get_conversations_with_pending_messages()
      for conv in conversations:
          await run_purchase_agent(conv.user_identifier, conv.channel)
  
  if __name__ == "__main__":
      scheduler = AsyncIOScheduler()
      scheduler.add_job(
          run_agent_for_all_conversations,
          'interval',
          minutes=5
      )
      scheduler.start()
      asyncio.get_event_loop().run_forever()
  ```
- [ ] Add health check endpoint:
  ```python
  @router.get("/health/purchase-agent")
  async def health_check_agent():
      # Check Odoo connectivity
      # Check database connectivity
      # Check pending message backlog
      return {"status": "healthy", "timestamp": datetime.now()}
  ```
- [ ] Commit: `feat(phase3): add deployment configuration`

---

### **Task 3.5.6 — Documentation**

- [ ] Create `src/purchase_agent/README.md`:
  ```markdown
  # Purchase Order Handler Agent
  
  LangGraph agent for automated purchase order negotiation via Chatwoot.
  
  ## Architecture
  
  [Mermaid diagram]
  
  ## Configuration
  
  [Environment variables]
  
  ## Workflows
  
  ### Create RFQ
  [Step-by-step explanation]
  
  ### Confirm Order
  [Step-by-step explanation]
  
  ## Testing
  
  [How to run tests]
  
  ## Deployment
  
  [Deployment steps]
  
  ## Troubleshooting
  
  [Common issues and solutions]
  ```
- [ ] Create architecture diagram:
  ```mermaid
  graph TD
      A[Provider WhatsApp] -->|Message| B[Chatwoot]
      B -->|Webhook| C[Processor]
      C -->|Store| D[(Postgres)]
      D -->|Read| E[Purchase Agent]
      E -->|Create Order| F[Odoo]
      F -->|Status| E
      E -->|Queue Reply| D
      D -->|Read| C
      C -->|Send| B
      B -->|Message| A
  ```
- [ ] Create deployment runbook:
  ```markdown
  # Deployment Runbook
  
  ## Pre-deployment Checklist
  - [ ] Database migrations applied
  - [ ] Environment variables configured
  - [ ] Odoo connectivity verified
  - [ ] Tests passing
  
  ## Deployment Steps
  1. ...
  
  ## Rollback Procedure
  1. ...
  
  ## Post-deployment Validation
  - [ ] Health check passing
  - [ ] Metrics endpoint responding
  - [ ] Sample order creation successful
  ```
- [ ] Create troubleshooting guide:
  ```markdown
  # Troubleshooting Guide
  
  ## Agent not processing messages
  - Check scheduler logs
  - Verify database connectivity
  - Check message status in Postgres
  
  ## Odoo API failures
  - Verify credentials
  - Check network connectivity
  - Review circuit breaker status
  
  ## ...
  ```
- [ ] Update main README with Phase 3 status
- [ ] Commit: `docs(phase3): add comprehensive documentation`

---

### **Phase 3.5 Completion Criteria:**

- [ ] Structured JSON logging implemented
- [ ] Prometheus metrics exposed
- [ ] Error monitoring and Slack alerts configured
- [ ] Environment-based configuration
- [ ] Docker deployment updated
- [ ] Health check endpoint
- [ ] Scheduler for periodic runs
- [ ] Comprehensive documentation
- [ ] Architecture diagrams
- [ ] Deployment runbook
- [ ] Troubleshooting guide
- [ ] Production deployment tested

**Estimated Duration:** 3-5 días  
**Blockers:** Production infrastructure access  
**Dependencies:** Phase 3.4 complete

---

## ✅ **Phase 3 Final Checklist**

### **Deliverables:**

- [ ] OdooOrderManager protocol defined
- [ ] PostgresIOAdapter implemented
- [ ] OdooAdapter (real + mock) implemented
- [ ] LangGraph tools created
- [ ] Agent graph built and functional
- [ ] Business logic (intent, validation, workflows) implemented
- [ ] E2E integration tests (≥15 tests)
- [ ] Mock and real testing modes
- [ ] Structured logging
- [ ] Prometheus metrics
- [ ] Error monitoring
- [ ] Configuration management
- [ ] Docker deployment
- [ ] Documentation complete
- [ ] Production deployment validated

### **Quality Gates:**

- [ ] All tests passing (unit + integration + E2E)
- [ ] Test coverage ≥85%
- [ ] No critical security vulnerabilities
- [ ] Performance benchmarks met (<2s per order creation)
- [ ] Code reviewed by peer
- [ ] Documentation reviewed
- [ ] Staging environment validated
- [ ] Production dry-run successful

### **Sign-off:**

- [ ] Tech lead approval
- [ ] Product owner approval
- [ ] Deployment plan approved
- [ ] Monitoring dashboards configured
- [ ] On-call runbook distributed

---

## 📊 **Estimated Timeline Summary**

| Phase | Sub-phases | Duration | Dependencies |
|-------|-----------|----------|--------------|
| **3.1** | Protocols & Adapters | 3-5 días | odoo-api library |
| **3.2** | LangGraph Tools | 5-7 días | Phase 3.1 |
| **3.3** | Business Logic | 5-7 días | Phase 3.2 |
| **3.4** | Integration & Testing | 7-10 días | Phase 3.3 |
| **3.5** | Monitoring & Deployment | 3-5 días | Phase 3.4 |
| **Total** | **All sub-phases** | **23-34 días** (~3-4 semanas) | |

---

## 🚀 **Next Actions**

1. **Immediate (Day 1):**
   - [ ] Verify `odoo-api` library status and documentation
   - [ ] Set up development branch: `feature/phase3-purchase-agent`
   - [ ] Create project structure:
     ```bash
     mkdir -p src/purchase_agent/{protocols,adapters,tools,graph,workflows}
     mkdir -p tests/purchase_agent/{adapters,integration,simulation}
     ```
   - [ ] Start Task 3.1.1 (Define OdooOrderManager Protocol)

2. **Week 1:**
   - Complete Phase 3.1 (Protocols & Adapters)
   - Begin Phase 3.2 (LangGraph Tools)

3. **Week 2:**
   - Complete Phase 3.2
   - Begin Phase 3.3 (Business Logic)

4. **Week 3:**
   - Complete Phase 3.3
   - Begin Phase 3.4 (Integration & Testing)

5. **Week 4:**
   - Complete Phase 3.4
   - Complete Phase 3.5 (Monitoring & Deployment)
   - Production deployment

---

**Document Status:** ✅ Ready for Implementation  
**Last Updated:** 12 de noviembre de 2025  
**Next Review:** End of Phase 3.1
