# identity/aria.py — Phase 2 Week 5: Tools integrated
import uuid, re
from identity.persona import get_persona
from identity.prompt_builder import build_system_prompt, detect_language
from graph.llm import get_llm
from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory
from langchain_core.messages import HumanMessage, SystemMessage


class Aria:
    def __init__(self):
        self.persona      = get_persona()
        self.llm          = get_llm(fast=False)
        self.history      = []
        self.session_id   = str(uuid.uuid4())
        self.turn_count   = 0
        self.episodic     = EpisodicMemory()
        self.semantic     = SemanticMemory()
        self._booking     = None
        self._crm         = None
        self._whatsapp    = None
        self._email       = None
        self.customer_info = {"name": "", "phone": "", "address": "", "issue": "", "email": ""}
        print(f"  [ARIA] Session: {self.session_id[:16]}...")

    @property
    def booking(self):
        if not self._booking:
            from tools.booking import BookingTool
            self._booking = BookingTool()
        return self._booking

    @property
    def crm(self):
        if not self._crm:
            from tools.crm import CRMTool
            self._crm = CRMTool()
        return self._crm

    @property
    def whatsapp(self):
        if not self._whatsapp:
            from tools.whatsapp import WhatsAppTool
            self._whatsapp = WhatsAppTool()
        return self._whatsapp

    @property
    def email(self):
        if not self._email:
            from tools.email_tool import EmailTool
            self._email = EmailTool()
        return self._email

    def chat(self, user_message: str, mode: str = "auto", context: str = "") -> dict:
        self.turn_count += 1
        lang = detect_language(user_message)
        if mode == "auto":
            mode = self._detect_mode(user_message)

        self._extract_info(user_message)

        if self.customer_info["phone"] and self.turn_count <= 3:
            self._save_lead_to_crm(mode)

        memory_context, memory_count = "", 0
        if self.turn_count == 1:
            try:
                memories = self.episodic.search(user_message, top_k=2)
                if memories:
                    memory_count = len(memories)
                    memory_context = "Past interactions:\n" + "\n".join(
                        f"- {m['content'][:150]}" for m in memories)
            except Exception:
                pass

        full_context  = "\n\n".join(filter(None, [context, memory_context]))
        system_prompt = build_system_prompt(persona=self.persona, context=full_context, mode=mode)
        self.history.append(HumanMessage(content=user_message))
        messages = [SystemMessage(content=system_prompt)] + self.history

        try:
            response = self.llm.invoke(messages)
            reply    = response.content
            self.history.append(response)
        except Exception:
            reply = ("Aapki baat samajh gayi, lekin abhi technical issue hai. Thoda wait karein."
                     if lang == "hindi" else "Technical issue. Please wait.")

        booking_result = None
        if self._should_book(user_message, reply):
            booking_result = self._do_booking()

        return {"response": reply, "language": lang, "mode": mode,
                "persona": f"{self.persona.name} — {self.persona.company}",
                "memory": memory_count, "booking": booking_result,
                "customer_info": self.customer_info}

    def _extract_info(self, text: str) -> None:
        if m := re.search(r'\b[6-9]\d{9}\b', text):
            if not self.customer_info["phone"]:
                self.customer_info["phone"] = m.group()
        if m := re.search(r'\b[\w.-]+@[\w.-]+\.\w+\b', text):
            if not self.customer_info["email"]:
                self.customer_info["email"] = m.group()
        for pat in [r"(?:mera naam|main hoon|my name is|i am|i'm)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"]:
            if m := re.search(pat, text, re.IGNORECASE):
                if not self.customer_info["name"]:
                    self.customer_info["name"] = m.group(1).strip()
        if not self.customer_info["issue"] and len(text) > 10:
            self.customer_info["issue"] = text[:200]

    def _save_lead_to_crm(self, mode: str) -> None:
        try:
            info = self.customer_info
            if not info["phone"]: return
            self.crm.save_lead(
                name=info["name"] or "Unknown", phone=info["phone"],
                issue=info["issue"], address=info["address"],
                email=info["email"], source="chat_ui",
                notes=f"Mode:{mode} Session:{self.session_id[:8]}")
            self.crm.update_stage(info["phone"], "contacted", "Aria se baat hui")
        except Exception as e:
            print(f"  [ARIA] CRM failed: {e}")

    def _should_book(self, user_msg: str, reply: str) -> bool:
        signals = ["appointment book", "booking karo", "technician bhejo",
                   "slot chahiye", "kab aayenge", "aaj aa sakte", "kal aa sakte",
                   "book kar do"]
        text = (user_msg + " " + reply).lower()
        return any(s in text for s in signals) and bool(self.customer_info["phone"])

    def _do_booking(self) -> dict:
        try:
            info   = self.customer_info
            result = self.booking.book(
                name=info["name"] or "Customer", phone=info["phone"],
                address=info["address"] or "To be confirmed",
                service="AC Repair", preferred_date="tomorrow",
                slot="10:00 AM", notes=info["issue"][:100])
            if result["success"]:
                print(f"  [ARIA] Booked: {result['booking_id']}")
                if info["phone"]:
                    self.crm.update_stage(info["phone"], "appointment_booked", result["booking_id"])
                self.whatsapp.send_booking_confirm(
                    to=info["phone"],
                    booking={"booking_id": result["booking_id"], "name": info["name"] or "Customer",
                             "service": "AC Repair", "date": "Kal", "slot": "10:00 AM",
                             "address": info["address"] or ""})
                if info["email"]:
                    self.email.send_booking_confirm(to=info["email"],
                        booking={"booking_id": result["booking_id"], "name": info["name"],
                                 "service": "AC Repair", "date": "Kal", "slot": "10:00 AM",
                                 "address": info["address"]})
            return result
        except Exception as e:
            print(f"  [ARIA] Booking failed: {e}")
            return {"success": False, "error": str(e)}

    def greet(self) -> str:
        system_prompt = build_system_prompt(persona=self.persona, mode="greeting")
        try:
            r = self.llm.invoke([SystemMessage(content=system_prompt),
                                  HumanMessage(content="Greet customer warmly as Aria.")])
            return r.content
        except Exception:
            return self.persona.hindi_greeting

    def end_session(self, final_score: float = 0.9) -> None:
        if not self.history: return
        convo = " | ".join([m.content[:100] for m in self.history if hasattr(m, "content")])
        try:
            self.episodic.store(session_id=self.session_id, raw_input=convo[:300],
                synthesis=f"AC service {self.turn_count} turns", what_worked=f"{self.turn_count} turns",
                what_failed="", score=final_score, problem_type="customer_service")
            self.semantic.store_session(session_id=self.session_id, raw_input=convo[:300],
                problem_type="customer_service", final_score=final_score,
                what_worked=f"{self.turn_count} turns", what_failed="")
            print(f"  [ARIA] Session saved ✓")
        except Exception as e:
            print(f"  [ARIA] Memory save failed: {e}")

    def reset(self):
        self.end_session()
        self.history = []; self.turn_count = 0
        self.session_id = str(uuid.uuid4())
        self.customer_info = {"name": "", "phone": "", "address": "", "issue": "", "email": ""}

    def _detect_mode(self, text: str) -> str:
        t = text.lower()
        for p in ["thanda nahi","not working","kaam nahi","band ho","cooling nahi","gas khatam"]:
            if p in t: return "support"
        for p in ["amc plan","service plan","new ac","kitne ka","price kya","book karna"]:
            if p in t: return "sales"
        w = set(t.split())
        if w & {"band","problem","issue","leak","repair","fix","gas","thanda"}: return "support"
        if w & {"install","price","amc","book","appointment","plan"}: return "sales"
        return "general"