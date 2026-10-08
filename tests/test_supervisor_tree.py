from shibaclaw.agent.supervisor_tree import SupervisorTree

def test_supervisor_tree_register_and_start():
    tree = SupervisorTree()
    started = False
    
    def start_fn():
        nonlocal started
        started = True
        
    tree.register_child("test_child", start_fn)
    tree.start_all()
    
    assert started is True
    assert tree.children["test_child"].status == "running"

def test_supervisor_tree_restart_on_failure():
    tree = SupervisorTree()
    runs = 0
    
    def start_fn():
        nonlocal runs
        runs += 1
        if runs == 1:
            raise ValueError("Simulated failure")
            
    tree.register_child("test_child", start_fn, max_restarts=2, backoff_factor=0.1)
    tree.start_all()
    
    assert tree.children["test_child"].status == "failed"
    
    # Trigger manual failure handling
    tree.handle_child_failure("test_child")
    
    assert runs == 2
    assert tree.children["test_child"].status == "running"
