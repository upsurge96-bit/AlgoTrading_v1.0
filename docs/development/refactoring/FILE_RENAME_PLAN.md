# File Rename Plan - Data Service Module Reorganization

**Date**: October 19, 2025  
**Reason**: Eliminate confusing duplicate names between `extraction/` and `load/` directories

---

## 🎯 Renaming Strategy

### Current Problem
Both `extraction/` and `load/` have files named:
- `live_data.py` (confusing - which one handles what?)
- `historical_data.py` (confusing - which one does what?)

### Solution: Rename by Responsibility

| Current Path | New Path | Purpose |
|-------------|----------|---------|
| `extraction/live_data.py` | `extraction/websocket_client.py` | **Kite WebSocket client** for live tick streaming |
| `extraction/historical_data.py` | `extraction/kite_api_client.py` | **Kite REST API client** for historical candle fetching |
| `load/live_data.py` | `load/realtime_stream_processor.py` | **Real-time processor** that processes ticks and stores to TimescaleDB |
| `load/historical_data.py` | `load/historical_batch_loader.py` | **Batch loader** that fetches historical data and stores to MinIO |

---

## 📋 Detailed Renaming Steps

### Step 1: Rename Extraction Layer (Low-level API clients)

#### 1.1 `extraction/live_data.py` → `extraction/websocket_client.py`

**Files to Update**:
- `services/data_service/extraction/live_data.py` (rename file)
- `services/data_service/workers.py` (import statement)
- `services/data_service/load/realtime_stream_processor.py` (import statement)

**Classes Renamed**:
- `KiteWebSocketClient` (keep name - it's descriptive)

**Import Changes**:
```python
# OLD
from services.data_service.extraction.live_data import KiteWebSocketClient

# NEW
from services.data_service.extraction.websocket_client import KiteWebSocketClient
```

---

#### 1.2 `extraction/historical_data.py` → `extraction/kite_api_client.py`

**Files to Update**:
- `services/data_service/extraction/historical_data.py` (rename file)
- `services/data_service/workers.py` (import statement)
- `services/data_service/load/historical_batch_loader.py` (import statement)

**Classes Renamed**:
- `HistoricalDataFetcher` → `KiteHistoricalAPI` (clearer name)

**Import Changes**:
```python
# OLD
from services.data_service.extraction.historical_data import HistoricalDataFetcher

# NEW
from services.data_service.extraction.kite_api_client import KiteHistoricalAPI
```

---

### Step 2: Rename Load Layer (High-level processors)

#### 2.1 `load/live_data.py` → `load/realtime_stream_processor.py`

**Files to Update**:
- `services/data_service/load/live_data.py` (rename file)
- `services/data_service/load/__init__.py` (import/export)

**Classes Renamed**:
- `LiveDataProcessor` → `RealtimeStreamProcessor` (clearer name)

**Import Changes**:
```python
# OLD
from services.data_service.load.live_data import LiveDataProcessor

# NEW
from services.data_service.load.realtime_stream_processor import RealtimeStreamProcessor
```

---

#### 2.2 `load/historical_data.py` → `load/historical_batch_loader.py`

**Files to Update**:
- `services/data_service/load/historical_data.py` (rename file)
- `services/data_service/load/__init__.py` (import/export)
- `services/data_service/load/scheduler.py` (import statement)

**Classes Kept**:
- `HistoricalDataLoader` (already descriptive)

**Import Changes**:
```python
# OLD
from services.data_service.load.historical_data import HistoricalDataLoader

# NEW
from services.data_service.load.historical_batch_loader import HistoricalDataLoader
```

---

## 🔄 Execution Order

### Phase 1: Extraction Layer (No dependencies on load/)
1. Rename `extraction/live_data.py` → `extraction/websocket_client.py`
2. Update imports in `workers.py`
3. Rename `extraction/historical_data.py` → `extraction/kite_api_client.py`
4. Update imports in `workers.py`
5. Rename class `HistoricalDataFetcher` → `KiteHistoricalAPI`

### Phase 2: Load Layer (Depends on extraction/)
6. Rename `load/live_data.py` → `load/realtime_stream_processor.py`
7. Rename class `LiveDataProcessor` → `RealtimeStreamProcessor`
8. Update imports in `load/__init__.py`
9. Rename `load/historical_data.py` → `load/historical_batch_loader.py`
10. Update imports in `load/__init__.py` and `load/scheduler.py`

### Phase 3: Rebuild & Test
11. Rebuild Docker container: `docker-compose build data_service`
12. Restart service: `docker-compose up -d data_service`
13. Verify logs show no import errors
14. Test with `monitor_heartbeat.bat`

---

## 📝 Files to Modify (Summary)

| File | Changes |
|------|---------|
| `extraction/live_data.py` | **RENAME** → `websocket_client.py` |
| `extraction/historical_data.py` | **RENAME** → `kite_api_client.py` + class rename |
| `load/live_data.py` | **RENAME** → `realtime_stream_processor.py` + class rename |
| `load/historical_data.py` | **RENAME** → `historical_batch_loader.py` |
| `workers.py` | Update 2 imports |
| `load/__init__.py` | Update 2 imports |
| `load/scheduler.py` | Update 1 import |

**Total**: 4 file renames, 2 class renames, 7 import updates

---

## ✅ Benefits

1. **Clear Separation**: 
   - `extraction/` = Low-level API clients (WebSocket, REST)
   - `load/` = High-level processors (stream, batch)

2. **No Name Collisions**:
   - `websocket_client.py` vs `realtime_stream_processor.py` (clear!)
   - `kite_api_client.py` vs `historical_batch_loader.py` (clear!)

3. **Self-Documenting**:
   - File names explain purpose
   - No need to check directory to understand role

4. **Easier Maintenance**:
   - Developers know which file to edit
   - Imports are self-explanatory

---

## 🚀 Ready to Execute?

This plan will eliminate all confusion between duplicate file names while maintaining backward compatibility in class names where appropriate.

**Estimated Time**: 15 minutes  
**Risk Level**: Low (simple renames with import updates)  
**Rollback**: Git revert if issues arise
