from shibaclaw.agent.graceful_degradation import GracefulDegradation

def test_graceful_degradation_primary_success():
    gd = GracefulDegradation()
    
    def primary():
        return "primary_result"
        
    result = gd.execute_with_fallback("test_key", primary, [])
    assert result == "primary_result"
    assert gd._get_cached("test_key") == "primary_result"

def test_graceful_degradation_fallback_success():
    gd = GracefulDegradation()
    
    def primary():
        raise ValueError("Primary failed")
        
    def fallback():
        return "fallback_result"
        
    result = gd.execute_with_fallback("test_key", primary, [fallback])
    assert result == "fallback_result"
    assert gd._get_cached("test_key") == "fallback_result"

def test_graceful_degradation_cache_fallback():
    gd = GracefulDegradation()
    
    # Populate cache first
    gd._update_cache("test_key", "cached_result")
    
    def primary():
        raise ValueError("Primary failed")
        
    def fallback():
        raise ValueError("Fallback failed")
        
    result = gd.execute_with_fallback("test_key", primary, [fallback])
    assert result == "cached_result"
