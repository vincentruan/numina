"""数据库后端抽象基类"""

from abc import ABC, abstractmethod

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker


class DatabaseBackend(ABC):
    """数据库后端抽象基类"""

    @abstractmethod
    def get_connection_args(self) -> dict:
        """返回数据库特定的连接参数（传给 create_engine 的 connect_args）"""
        pass

    @abstractmethod
    def get_pool_config(self) -> dict:
        """返回连接池配置（传给 create_engine 的其他参数）"""
        pass

    def create_engine(self, url: str) -> Engine:
        """创建 SQLAlchemy Engine"""
        connection_args = self.get_connection_args()
        pool_config = self.get_pool_config()
        # connect_args 必须作为单独参数传递
        return create_engine(url, connect_args=connection_args, **pool_config)

    def create_session_factory(self, engine: Engine) -> sessionmaker:
        """创建 Session 工厂"""
        return sessionmaker(autocommit=False, autoflush=False, bind=engine)