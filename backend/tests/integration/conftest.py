"""集成测试配置 - Docker 容器启动 fixtures"""

import time
import pytest
import docker
from docker.errors import DockerException


def wait_for_container(container, timeout=60) -> bool:
    """等待容器健康检查通过"""
    start = time.time()
    while time.time() - start < timeout:
        container.reload()
        if container.status == "running":
            health = container.attrs.get("State", {}).get("Health", {})
            if health.get("Status") == "healthy":
                return True
        time.sleep(1)
    return False


@pytest.fixture(scope="session")
def docker_client():
    """Docker 客户端"""
    try:
        client = docker.from_env()
        yield client
    except DockerException:
        pytest.skip("Docker not available")


@pytest.fixture(scope="session")
def mysql_container(docker_client):
    """启动 MySQL Docker 容器"""
    container = docker_client.containers.run(
        "mysql:8.0",
        environment={
            "MYSQL_ROOT_PASSWORD": "testpass",
            "MYSQL_DATABASE": "test_numina",
            "MYSQL_USER": "test",
            "MYSQL_PASSWORD": "testpass",
        },
        ports={"3306/tcp": None},
        detach=True,
        auto_remove=True,
        healthcheck={
            "Test": ["CMD", "mysqladmin", "ping", "-h", "localhost"],
            "Interval": 1_000_000_000,  # 1秒
            "Timeout": 5_000_000_000,  # 5秒
            "Retries": 10,
        },
    )

    # 等待容器就绪
    if not wait_for_container(container, timeout=60):
        container.stop()
        pytest.fail("MySQL container failed to start")

    # 获取随机端口
    container.reload()
    port = container.attrs["NetworkSettings"]["Ports"]["3306/tcp"][0]["HostPort"]

    yield {
        "host": "localhost",
        "port": port,
        "user": "test",
        "password": "testpass",
        "database": "test_numina",
    }

    container.stop()


@pytest.fixture(scope="session")
def postgres_container(docker_client):
    """启动 PostgreSQL Docker 容器"""
    container = docker_client.containers.run(
        "postgres:15",
        environment={
            "POSTGRES_DB": "test_numina",
            "POSTGRES_USER": "test",
            "POSTGRES_PASSWORD": "testpass",
        },
        ports={"5432/tcp": None},
        detach=True,
        auto_remove=True,
        healthcheck={
            "Test": ["CMD-SHELL", "pg_isready -U test"],
            "Interval": 1_000_000_000,
            "Timeout": 5_000_000_000,
            "Retries": 10,
        },
    )

    if not wait_for_container(container, timeout=60):
        container.stop()
        pytest.fail("PostgreSQL container failed to start")

    container.reload()
    port = container.attrs["NetworkSettings"]["Ports"]["5432/tcp"][0]["HostPort"]

    yield {
        "host": "localhost",
        "port": port,
        "user": "test",
        "password": "testpass",
        "database": "test_numina",
    }

    container.stop()


@pytest.fixture
def mysql_url(mysql_container):
    """MySQL 连接 URL"""
    return (
        f"mysql+pymysql://{mysql_container['user']}:{mysql_container['password']}"
        f"@{mysql_container['host']}:{mysql_container['port']}/{mysql_container['database']}"
    )


@pytest.fixture
def postgres_url(postgres_container):
    """PostgreSQL 连接 URL"""
    return (
        f"postgresql+psycopg2://{postgres_container['user']}:{postgres_container['password']}"
        f"@{postgres_container['host']}:{postgres_container['port']}/{postgres_container['database']}"
    )