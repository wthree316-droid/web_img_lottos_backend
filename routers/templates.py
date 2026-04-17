from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from database import supabase, execute_supabase
from schemas import TemplateCreate, UploadResponse
import uuid

# สร้าง Router ตั้ง Prefix เป็น /api
router = APIRouter(prefix="/api", tags=["Templates & Uploads"])

@router.get("/templates")
def get_templates(owner_id: str = Query(None)):
    try:
        query = supabase.table("templates").select("*").order("created_at", desc=True)
        if owner_id:
            query = query.or_(f"owner_id.eq.{owner_id},owner_id.is.null")
        response = execute_supabase(query)
        return response.data
    except Exception as e:
        print(f"Get Templates Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/templates/{template_id}")
def get_template(template_id: str):
    try:
        response = execute_supabase(
            supabase.table("templates")
            .select("*, template_slots(*), template_backgrounds(*)")
            .eq("id", template_id)
            .limit(1)
        )
            
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=404, detail="Template not found")
            
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        print(f"Get Template Detail Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/templates")
def create_template(request: TemplateCreate):
    try:
        template_data = {
            "name": request.name,
            "base_width": request.width,   
            "base_height": request.height, 
            "background_url": request.background_url,
            "is_master": request.is_master,
            "owner_id": None, # Default None
            "is_active": True
        }
        res_template = execute_supabase(supabase.table("templates").insert(template_data))
        if not res_template.data: raise HTTPException(status_code=500, detail="Failed to save template")
        new_template_id = res_template.data[0]['id']

        slots_data = []
        for slot in request.slots:
            slots_data.append({
                "template_id": new_template_id,
                "slot_type": slot.type,    
                "label_text": slot.content, 
                "data_key": slot.data_key,
                "pos_x": slot.x, "pos_y": slot.y,           
                "width": slot.width, "height": slot.height,
                "style_config": slot.style, "z_index": 1
            })
        if slots_data: execute_supabase(supabase.table("template_slots").insert(slots_data))

        backgrounds_data = []
        if request.backgrounds:
            for bg in request.backgrounds:
                backgrounds_data.append({
                    "template_id": new_template_id,
                    "name": bg.name, "url": bg.url
                })
            execute_supabase(supabase.table("template_backgrounds").insert(backgrounds_data))

        return {"message": "Saved successfully!", "id": new_template_id}
    except Exception as e:
        print("Create Template Error:", e) 
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/templates/{template_id}")
def update_template(template_id: str, request: TemplateCreate):
    try:
        template_data = {
            "name": request.name,
            "base_width": request.width,
            "base_height": request.height,
            "background_url": request.background_url,
            "is_master": request.is_master,
            "owner_id": request.owner_id if hasattr(request, 'owner_id') and request.owner_id else None,
            "updated_at": "now()" 
        }
        execute_supabase(supabase.table("templates").update(template_data).eq("id", template_id))
        
        execute_supabase(supabase.table("template_slots").delete().eq("template_id", template_id))
        execute_supabase(supabase.table("template_backgrounds").delete().eq("template_id", template_id))

        slots_data = []
        for slot in request.slots:
            slots_data.append({
                "template_id": template_id, "slot_type": slot.type,
                "label_text": slot.content, "data_key": slot.data_key,
                "pos_x": slot.x, "pos_y": slot.y,
                "width": slot.width, "height": slot.height,
                "style_config": slot.style, "z_index": 1
            })
        if slots_data: execute_supabase(supabase.table("template_slots").insert(slots_data))

        backgrounds_data = []
        if request.backgrounds:
            for bg in request.backgrounds:
                backgrounds_data.append({
                    "template_id": template_id, "name": bg.name, "url": bg.url
                })
            execute_supabase(supabase.table("template_backgrounds").insert(backgrounds_data))

        return {"message": "Updated successfully!"}
    except Exception as e:
        print("Update Template Error:", e) 
        raise HTTPException(status_code=500, detail=str(e))    

@router.delete("/templates/{template_id}")
def delete_template(template_id: str):
    try:
        # 1. ค้นหารูปภาพที่เชื่อมโยงกับแม่พิมพ์นี้ก่อน (ภาพหลัก + ภาพทางเลือก)
        urls_to_delete = []
        
        # ดึงภาพหลัก
        temp_res = execute_supabase(supabase.table("templates").select("background_url").eq("id", template_id).limit(1))
        if temp_res.data and temp_res.data[0].get("background_url"):
            urls_to_delete.append(temp_res.data[0]["background_url"])
            
        # ดึงภาพทางเลือก
        bg_res = execute_supabase(supabase.table("template_backgrounds").select("url").eq("template_id", template_id))
        if bg_res.data:
            for bg in bg_res.data:
                if bg.get("url"):
                    urls_to_delete.append(bg["url"])

        # 2. ลบข้อมูลออกจาก Database
        execute_supabase(supabase.table("template_slots").delete().eq("template_id", template_id))
        execute_supabase(supabase.table("template_backgrounds").delete().eq("template_id", template_id))
        execute_supabase(supabase.table("templates").delete().eq("id", template_id))

        # 3. ลบไฟล์ใน Supabase Storage
        if urls_to_delete:
            paths_to_delete = []
            for url in urls_to_delete:
                if "lotto-assets/" in url:
                    file_path = url.split("lotto-assets/")[1]
                    paths_to_delete.append(file_path)
            
            if paths_to_delete:
                try:
                    supabase.storage.from_("lotto-assets").remove(paths_to_delete)
                except Exception as storage_err:
                    print(f"⚠️ Failed to delete images from storage: {storage_err}")

        return {"message": "Deleted successfully and cleaned up storage"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload", response_model=UploadResponse)
async def upload_image(file: UploadFile = File(...)):
    try:
        file_content = await file.read()
        file_ext = file.filename.split(".")[-1]
        file_path = f"backgrounds/{uuid.uuid4()}.{file_ext}"
        bucket_name = "lotto-assets"
        
        supabase.storage.from_(bucket_name).upload(
            path=file_path, file=file_content,
            file_options={"content-type": file.content_type}
        )
        public_url = supabase.storage.from_(bucket_name).get_public_url(file_path)
        return {"url": public_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")