"""接口返回格式"""


def success_response(item=None, total=1, status=1, message="success"):
    """成功返回数据格式"""
    return {"status": status, "message": message, "item": item, "total": total}


def failure_response(item=None, total=0, status=0, message=None):
    """失败返回数据格式"""
    if message is None:
        message = "failure"
    else:
        message = f"failure: {message}"

    return {"status": status, "message": message, "item": item, "total": total}

