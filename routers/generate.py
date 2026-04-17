from fastapi import APIRouter, HTTPException
from database import supabase, execute_supabase
from schemas import GenerateRequest, GenerateResponse
from logic import LotteryLogic

router = APIRouter(prefix="/api/generate", tags=["Generate Engine"])

@router.post("", response_model=GenerateResponse)
def generate_numbers(request: GenerateRequest):
    try:
        engine = LotteryLogic(seed=request.user_seed)
        final_qr = ""
        final_line = ""

        # 1. User Override (Priority 1)
        if request.target_user_id:
            try:
                u_res = execute_supabase(supabase.table("users").select("custom_qr_code_url, custom_line_id").eq("id", request.target_user_id).limit(1))
                if u_res.data and len(u_res.data) > 0:
                    user_data = u_res.data[0]
                    if user_data.get("custom_qr_code_url"):
                        final_qr = user_data["custom_qr_code_url"]
                    if user_data.get("custom_line_id"):
                        final_line = user_data["custom_line_id"]
            except Exception as e:
                print("Fallback Config Error:", e)

        results = {}
        for slot in request.slot_configs:
            slot_id = slot.get("id")
            slot_type = slot.get("slot_type")
            data_key = slot.get("data_key")

            if slot_type == "user_input" and data_key:
                if slot_id: results[slot_id] = engine.generate(data_key)
            elif slot_type == "qr_code":
                if slot_id: results[slot_id] = final_qr
            elif slot_type == "static_text" and data_key == "line_id":
                if slot_id: results[slot_id] = final_line

        return {"results": results}
    except Exception as e:
        print(f"Generate Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))