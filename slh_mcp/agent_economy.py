                after=target_after,
                actor=str(actor),
                reason=reason,
                entry_type="transfer_credit",
                meta=meta,
            )
            result = {
                "status": "completed",
                "operation_id": operation_id,
                "source_agent": source_agent,
                "target_agent": target_agent,
                "amount": amount,
                "source_balance": source_after,
                "target_balance": target_after,
            }
            self._record_operation(state, operation_id, fingerprint, result)
            self._write(state)
            return result

    def treasury_fund(self, *, agent_id, amount, operation_id, actor, reason, meta=None) -> dict:
        return self.transfer(
            source_agent=TREASURY_ACCOUNT,
            target_agent=str(agent_id),
            amount=amount,
            operation_id=operation_id,
            actor=actor,
            reason=reason,
            meta=meta,
        )

    def propose_transfer(
        self,
        *,
        source_agent,
        target_agent,
        amount,
        operation_id,
        actor,
        reason,
        meta=None,
    ) -> dict:
        source_agent = str(source_agent).strip()
        target_agent = str(target_agent).strip()
        operation_id = str(operation_id).strip()
        amount = float(amount)
        if not source_agent or not target_agent:
            raise ValueError("INVALID_AGENT_ACCOUNT")
        if source_agent == target_agent:
            raise ValueError("SELF_TRANSFER")
        if not operation_id:
            raise ValueError("INVALID_OPERATION_ID")
        if amount <= 0:
            raise ValueError("INVALID_TRANSFER_AMOUNT")
        payload = {
            "type": "proposal",
            "source_agent": source_agent,
            "target_agent": target_agent,
            "amount": amount,
            "actor": str(actor),
            "reason": str(reason),
            "meta": dict(meta or {}),
        }
        with self._lock:
            state = self._load()
            if operation_id in state["operations"]:
                raise ValueError("OPERATION_ID_ALREADY_USED")
            balance = float(state["accounts"].get(source_agent, 0.0))
            if balance < amount:
                raise ValueError("INSUFFICIENT_AGENT_ECONOMY")
            return {
                "status": "proposed",
                "operation_id": operation_id,
                "source_agent": source_agent,
                "target_agent": target_agent,
                "amount": amount,
                "source_balance": balance,
                "fingerprint": self._operation_fingerprint(payload),
            }

    def record_reward(
        self,
        *,
        agent_id,
        amount,
        operation_id,
        mission_id,
        actor,
        meta=None,
    ) -> dict:
        mission_id = str(mission_id).strip()
        if not mission_id:
            raise ValueError("INVALID_MISSION_ID")
        return self.treasury_fund(
            agent_id=str(agent_id).strip(),
            amount=float(amount),
            operation_id=str(operation_id).strip(),
            actor=actor,
            reason="mission:agent_reward",
            meta={"mission_id": mission_id, **dict(meta or {})},
        )
