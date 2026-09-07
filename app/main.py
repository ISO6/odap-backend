from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.exception import register_exceptions
from app.domains.splice_control.api import router as splice_control_router
from app.middleware.request_log import request_log_middleware

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    # 打印配置
    if settings.DEBUG:
        print(settings.model_dump())

    # 初始化数据库
    # await db_manager.init()

    # 初始化Redis
    # await redis_manager.init()

    yield
    # shutdown
    # 关闭Redis
    # await redis_manager.close()

    # 关闭数据库连接池
    # await db_manager.dispose()


app = FastAPI(title="ODAP Backend", version="2.0.0", lifespan=lifespan)

# 跨越问题
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 注册异常处理器
register_exceptions(app)
# 注册日志中间件
app.middleware("http")(request_log_middleware)

app.include_router(splice_control_router, prefix="/api/v1")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8001, reload=True)
