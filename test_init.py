import sys
sys.path.insert(0, '.')
from main import GoldAIEngine
print("Creating engine...")
engine = GoldAIEngine()
print("Engine created successfully.")
print("Testing strategy analysis with dummy data...")
import pandas as pd
import numpy as np
# Create dummy OHLCV data
close = 2300 + np.cumsum(np.random.normal(0, 1.5, 300))
open_ = close + np.random.normal(0, 0.8, 300)
high = np.maximum(open_, close) + np.abs(np.random.normal(0.8, 0.4, 300))
low = np.minimum(open_, close) - np.abs(np.random.normal(0.8, 0.4, 300))
df = pd.DataFrame({
    'open': open_,
    'high': high,
    'low': low,
    'close': close,
    'volume': np.random.rand(300)*100
})
# We'll need to monkey-patch mt5 to avoid connection; but we can just call strategy directly
from strategies.hybrid_strategy import HybridStrategy
strategy = HybridStrategy(engine.config["params"])
result = strategy.analyze(df)
print("Analysis result:", result)
print("Test completed.")
