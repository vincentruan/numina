"""Test that contextvars are properly propagated through the patched sync wrapper."""
import asyncio
import contextvars
from concurrent.futures import ThreadPoolExecutor

# Simulate the contextvar that DeerFlow uses
test_config_var = contextvars.ContextVar('test_config', default='default_value')

# Import the patched wrapper
from apps.agent.services.deerflow_adapter.sync_tool_patch import apply_sync_tool_patches
apply_sync_tool_patches()

from deerflow.tools.sync import make_sync_tool_wrapper

# Create an async function that reads the contextvar
async def async_tool_func():
    """Simulates an async tool that needs access to contextvars."""
    # This should see the contextvar value from the calling thread
    return test_config_var.get()

# Create sync wrapper
sync_wrapper = make_sync_tool_wrapper(async_tool_func, "test_tool")

# Test 1: Call from main thread with default contextvar
result1 = sync_wrapper()
print(f"Test 1 - Default context: {result1}")
assert result1 == "default_value", f"Expected 'default_value', got {result1}"

# Test 2: Call from a different thread with modified contextvar
def run_in_thread():
    # Set a different value in this thread's context
    test_config_var.set("thread_specific_value")
    # Call the sync wrapper - it should propagate this context
    return sync_wrapper()

with ThreadPoolExecutor(max_workers=1) as executor:
    future = executor.submit(run_in_thread)
    result2 = future.result()
    print(f"Test 2 - Thread context: {result2}")
    assert result2 == "thread_specific_value", f"Expected 'thread_specific_value', got {result2}"

# Test 3: Call from yet another thread with different context
def run_in_another_thread():
    test_config_var.set("another_value")
    return sync_wrapper()

with ThreadPoolExecutor(max_workers=1) as executor:
    future = executor.submit(run_in_another_thread)
    result3 = future.result()
    print(f"Test 3 - Another thread context: {result3}")
    assert result3 == "another_value", f"Expected 'another_value', got {result3}"

print("\n✓ All contextvar propagation tests passed!")
