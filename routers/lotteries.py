from fastapi import APIRouter, HTTPException, Query
from database import supabase, execute_supabase
from schemas import LotteryUpdate, LotteryCreate

# สร้าง Router ตั้ง Prefix เป็น /api/lotteries
router = APIRouter(prefix="/api/lotteries", tags=["Lotteries"])

@router.get("")
def get_lotteries(search: str = Query(None)):
    try:
        query = supabase.table("lotteries")\
            .select("*, templates(background_url, base_width, base_height)")\
            .eq("is_active", True)
        if search: query = query.ilike("name", f"%{search}%")
        response = execute_supabase(query.order("closing_time", desc=False))
        return response.data
    except Exception as e:
        print("Get Lotteries Error:", e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{lottery_id}")
def get_lottery_details(lottery_id: str, user_id: str = None):
    try:
        # 1. Fetch Lottery
        lottery_res = execute_supabase(supabase.table("lotteries").select("*").eq("id", lottery_id).limit(1))
        if not lottery_res.data: raise HTTPException(status_code=404, detail="Lottery not found")
        lottery = lottery_res.data[0]
        
        target_template_id = None

        # 2. Priority: User Assigned Template
        if user_id:
            try:
                u = execute_supabase(supabase.table("users").select("assigned_template_id").eq("id", user_id).limit(1))
                if u.data and u.data[0].get('assigned_template_id'): 
                    target_template_id = u.data[0]['assigned_template_id']
                
                # 2.1 Auto-Detect Owner
                if not target_template_id:
                    t = execute_supabase(supabase.table("templates").select("id").eq("owner_id", user_id).order("created_at", desc=True).limit(1))
                    if t.data:
                        target_template_id = t.data[0]['id']
            except: pass
        
        # 3. Fallback: Lottery Assigned
        if not target_template_id: target_template_id = lottery.get('template_id')
        
        # 4. Fallback: System Master
        if not target_template_id:
            try:
                l = execute_supabase(supabase.table("templates").select("id").eq("is_active", True).eq("is_master", True).limit(1))
                if l.data: target_template_id = l.data[0]['id']
            except: pass
            
        if not target_template_id: return {"lottery": lottery, "template": None}

        # 5. Fetch Template Detail
        template_res = execute_supabase(supabase.table("templates")\
            .select("*, template_slots(*), template_backgrounds(*)")\
            .eq("id", target_template_id).limit(1))
            
        if not template_res.data: return {"lottery": lottery, "template": None}
        
        return { "lottery": lottery, "template": template_res.data[0], "used_template_id": target_template_id }
    except Exception as e:
        print(f"Get Lottery Details Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("")
def create_lottery(request: LotteryCreate):
    try:
        data = {
            "name": request.name,
            "template_id": request.template_id if request.template_id else None,
            "closing_time": request.closing_time,
            "is_active": request.is_active,
            "icon_url": request.icon_url
        }
        res = execute_supabase(supabase.table("lotteries").insert(data))
        return {"message": "Created successfully", "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.put("/{lottery_id}")
def update_lottery(lottery_id: str, request: LotteryUpdate):
    try:
        update_data = {}
        if request.name is not None: update_data["name"] = request.name
        if request.closing_time is not None: update_data["closing_time"] = request.closing_time
        if request.is_active is not None: update_data["is_active"] = request.is_active
        if request.template_id is not None: update_data["template_id"] = request.template_id if request.template_id else None
        if request.icon_url is not None: update_data["icon_url"] = request.icon_url
        
        if update_data: execute_supabase(supabase.table("lotteries").update(update_data).eq("id", lottery_id))
        return {"message": "Updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{lottery_id}")
def delete_lottery(lottery_id: str):
    try:
        execute_supabase(supabase.table("lotteries").delete().eq("id", lottery_id))
        return {"message": "Deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))