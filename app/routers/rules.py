from fastapi import APIRouter, HTTPException
from typing import List
import yaml
from ..core.config import get_settings
from ..models.schemas import RuleItem

router = APIRouter(prefix="/rules", tags=["rules"])

def _rules_path():
    return get_settings().RULES_PATH

def _load_rules():
    with open(_rules_path(), "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("rules", [])

def _save_rules(rules):
    with open(_rules_path(), "w", encoding="utf-8") as f:
        yaml.safe_dump({"rules": rules}, f, allow_unicode=True, sort_keys=False)

@router.get("/", response_model=List[RuleItem])
def list_rules():
    return _load_rules()

@router.put("/", response_model=List[RuleItem])
def replace_rules(rules: List[RuleItem]):
    _save_rules([r.model_dump() for r in rules])
    return _load_rules()

@router.post("/", response_model=RuleItem, status_code=201)
def add_rule(rule: RuleItem):
    rules = _load_rules()
    if any(r["id"] == rule.id for r in rules):
        raise HTTPException(400, f"Rule id {rule.id} already exists.")
    rules.append(rule.model_dump())
    _save_rules(rules)
    return rule

@router.delete("/{rule_id}")
def delete_rule(rule_id: str):
    rules = _load_rules()
    rules = [r for r in rules if r["id"] != rule_id]
    _save_rules(rules)
    return {"deleted": rule_id}

