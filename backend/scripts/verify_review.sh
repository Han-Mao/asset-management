#!/bin/bash
# 对运行中的服务做一轮权限/流程端到端校验（curl + 输出关键字段）
B=http://127.0.0.1:8000/api
PY="C:/Users/adminer/.workbuddy/binaries/python/envs/asset-mgmt/Scripts/python.exe"

tok() {
  curl -s -X POST $B/auth/login -H 'Content-Type: application/json' \
    -d "{\"username\":\"$1\",\"password\":\"123456\"}" \
    | $PY -c "import sys,json;print(json.load(sys.stdin)['data']['access_token'])"
}

code() { $PY -c "import sys,json;d=json.load(sys.stdin);print(d.get('code'), (d.get('data') or {}).get('status') if isinstance(d.get('data'),dict) else '', d.get('message',''))"; }
val()  { $PY -c "import sys,json;d=json.load(sys.stdin)['data'];print(json.dumps(d,ensure_ascii=False)[:180])"; }

A=$(tok admin); Z=$(tok zhangsan); L=$(tok lisi)
AH="Authorization: Bearer $A"; ZH="Authorization: Bearer $Z"; LH="Authorization: Bearer $L"

# 找一台张三正在领用的资产
TARGET=$(curl -s -H "$AH" "$B/assets?status=BORROWED&borrower_id=2&page_size=1" | $PY -c "import sys,json;print(json.load(sys.stdin)['data']['items'][0]['id'])")
IN_STOCK=$(curl -s -H "$AH" "$B/assets?status=IN_STOCK&page_size=1" | $PY -c "import sys,json;print(json.load(sys.stdin)['data']['items'][0]['id'])")
echo "目标资产：张三领用的 #$TARGET ; 在库资产 #$IN_STOCK"

echo "--- 1. 张三本人看自己的设备（期望 0 BORROWED）"
curl -s -H "$ZH" "$B/assets/$TARGET" | code
echo "--- 2. 李四看张三的设备详情/生命周期/二维码（期望全 40301）"
curl -s -H "$LH" "$B/assets/$TARGET" | code
curl -s -H "$LH" "$B/assets/$TARGET/lifecycle" | code
curl -s -H "$LH" "$B/assets/$TARGET/qrcode" | code
echo "--- 3. 李四看在库资产（期望 0 IN_STOCK）"
curl -s -H "$LH" "$B/assets/$IN_STOCK" | code
echo "--- 4. 李四报修张三的设备和在库设备（期望 40301）；张三报修自己的（期望 PENDING）"
curl -s -H "$LH" -X POST "$B/repairs" -H 'Content-Type: application/json' -d "{\"asset_id\":$TARGET,\"fault_description\":\"坏了\"}" | code
curl -s -H "$LH" -X POST "$B/repairs" -H 'Content-Type: application/json' -d "{\"asset_id\":$IN_STOCK,\"fault_description\":\"坏了\"}" | code
REPAIR_ID=$(curl -s -H "$ZH" -X POST "$B/repairs" -H 'Content-Type: application/json' -d "{\"asset_id\":$TARGET,\"fault_description\":\"无法开机\"}" | $PY -c "import sys,json;d=json.load(sys.stdin);print(d['data']['id'] if d['code']==0 else 'ERR:'+d['message'])")
echo "  张三报修结果：$REPAIR_ID"
echo "--- 5. 李四看张三的维修单（期望 40301），管理员看（期望 0）"
curl -s -H "$LH" "$B/repairs/$REPAIR_ID" | code
curl -s -H "$AH" "$B/repairs/$REPAIR_ID" | code

echo "--- 6. 报废必须两步"
curl -s -H "$AH" -X POST "$B/assets/$IN_STOCK/scrap" | code
curl -s -H "$AH" -X POST "$B/assets/$IN_STOCK/pending-scrap" | code
curl -s -H "$AH" -X POST "$B/assets/$IN_STOCK/scrap" | code

echo "--- 7. 到期提醒两次调用（第一次有 expire/overdue，第二次里程碑为 0，逾期同日为 0）"
curl -s -H "$AH" -X POST "$B/system/reminders/test" | val
curl -s -H "$AH" -X POST "$B/system/reminders/test" | val
echo "--- 8. 我的设备 current=true 只含 ACTIVE/OVERDUE"
curl -s -H "$ZH" "$B/assignments/my?current=true&page_size=100" | $PY -c "import sys,json;d=json.load(sys.stdin)['data'];print(d['total'], sorted({i['status'] for i in d['items']}))"
echo "--- 9. 导入只收 .xlsx"
curl -s -H "$AH" -X POST "$B/assets/import" -F "file=@/dev/null;filename=x.xlsm" | code
echo "--- 10. 部门防环"
curl -s -H "$AH" -X PUT "$B/departments/1" -H 'Content-Type: application/json' -d '{"parent_id":2}' | code
