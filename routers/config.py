from fastapi import APIRouter, HTTPException
from database import supabase, execute_supabase
from schemas import GlobalConfigUpdate, GlobalConfigResponse

router = APIRouter(prefix="/api/global-configs", tags=["Global Configs"])

@router.get("", response_model=GlobalConfigResponse)
def get_global_configs():
    try:
        response = execute_supabase(supabase.table("global_configs").select("*"))
        configs = {item['key']: item['value'] for item in response.data}
        return {
            "qr_code_url": configs.get("qr_code_url", ""),
            "line_id": configs.get("line_id", "")
        }
    except Exception as e:
        return {"qr_code_url": "", "line_id": ""}

@router.put("")
def update_global_configs(config: GlobalConfigUpdate):
    try:
        if config.qr_code_url is not None:
            execute_supabase(supabase.table("global_configs").upsert({"key": "qr_code_url", "value": config.qr_code_url}))
        if config.line_id is not None:
            execute_supabase(supabase.table("global_configs").upsert({"key": "line_id", "value": config.line_id}))
        return {"message": "Updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))