# Real-Time Claims Update Protocol

## Overview
This document describes the Server-Sent Events (SSE) protocol for real-time claim updates in the receipt splitter application.

## Architecture
- **Transport**: Server-Sent Events (SSE) over HTTP
- **Message Broker**: Redis Pub/Sub for multi-worker coordination
- **Format**: JSON-encoded event data
- **Channels**: One SSE endpoint per receipt

## SSE Message Generation Triggers

Messages are generated when:
1. **Item claimed** - User successfully claims items
2. **Item unclaimed** - User removes their claim
3. **Receipt finalized** - Uploader finalizes the receipt (if not already)
4. **Heartbeat** - Every 30 seconds to keep connection alive

## SSE Message Format

### Event Types and Payloads

```javascript
// 1. Claims Update Event
event: claims_update
data: {
  "type": "claims_update",
  "receipt_id": "uuid",
  "timestamp": "2025-01-17T10:30:00Z",
  "version": 1234567890,  // Unix timestamp in ms for ordering
  "claims": [
    {
      "claim_id": "uuid",
      "line_item_id": "uuid", 
      "claimer_name": "John",
      "quantity_claimed": 2,
      "item_name": "Pizza"
    }
  ],
  "participant_totals": {
    "John": 25.50,
    "Jane": 18.75,
    "Bob": 32.00
  },
  "items_availability": {
    "item_id_1": {"available": 2, "total": 5},
    "item_id_2": {"available": 0, "total": 3}
  },
  "total_unclaimed": 15.25
}

// 2. Heartbeat Event
event: heartbeat
data: {"type": "heartbeat", "timestamp": "2025-01-17T10:30:00Z"}

// 3. Error Event
event: error
data: {"type": "error", "message": "Receipt not found", "code": "RECEIPT_404"}
```

## Client Behavior on Message Receipt

### On `claims_update` Event:
1. **Validate version** - Check if message version > last processed version
2. **Update participant totals** - Replace entire participants list
3. **Update item availability** - For each item:
   - Update available quantity display
   - Update max attribute on claim inputs
   - Show/hide "Fully Claimed" labels
   - Update claimed-by badges
4. **Update user's total** - Recalculate if current user has claims
5. **Update UI state**:
   - Show success image if all items claimed
   - Update "Not Claimed" amount
   - Clear any stale claim inputs (set to 0 if item unavailable)
6. **Store version** - Save message version as last processed

### On `heartbeat` Event:
- Reset connection timeout timer
- No UI updates needed

### On `error` Event:
- Log error for debugging
- If critical error, show user notification
- Consider fallback to polling

## Connection Management

### Initial Connection:
```javascript
const eventSource = new EventSource(`/sse/${receiptSlug}/`);
eventSource.addEventListener('claims_update', handleClaimsUpdate);
eventSource.addEventListener('heartbeat', handleHeartbeat);
eventSource.addEventListener('error', handleError);
```

### Reconnection Strategy:
- Browser automatically reconnects SSE on disconnect
- On reconnect, server sends full current state
- Client uses version number to detect if updates were missed

## Handling Lost Messages

### Detection:
- Version numbers are monotonically increasing timestamps
- If received version has gap from last processed, messages were lost

### Recovery:
1. **On version gap detected**:
   - Log warning about missed updates
   - Request full state refresh via GET `/data/<receipt_slug>/`
   - Apply full state to UI

2. **On connection error**:
   - After 3 failed reconnection attempts
   - Fall back to polling every 5 seconds
   - Show "Connection unstable" indicator

3. **Periodic validation**:
   - Every 60 seconds, validate local state matches server
   - If mismatch detected, request full refresh

### Fallback Polling Mode:
```javascript
// If SSE fails repeatedly
async function pollForUpdates() {
  const response = await fetch(`/data/${receiptSlug}/`);
  const data = await response.json();
  applyFullStateUpdate(data);
  setTimeout(pollForUpdates, 5000);
}
```

## Race Condition Handling

### Scenario: Two users claim last item simultaneously
1. User A and User B both see 1 item available
2. Both submit claims at same time
3. User A's claim succeeds
4. User B's claim fails with `InsufficientQuantityError`
5. User B receives SSE update showing item unavailable
6. User B's UI updates to show error and correct state

### Client-side Optimistic Updates:
- DO NOT apply optimistic updates for claims
- Wait for server confirmation via SSE
- This prevents UI inconsistencies

## Security Considerations

- SSE endpoint requires same session validation as view page
- No sensitive data in SSE messages (same data as view page)
- Rate limiting on SSE connections (max 5 per session)
- Automatic disconnect idle connections after 5 minutes

## Performance Considerations

- Full state updates are acceptable (receipt data < 10KB)
- Heartbeat every 30 seconds to detect stale connections
- Redis pub/sub ensures minimal latency between workers
- Message versioning prevents duplicate processing

## Testing Requirements

1. **Multi-tab testing**: Open 3+ tabs, verify all update simultaneously
2. **Network interruption**: Disconnect/reconnect, verify recovery
3. **Worker restart**: Kill worker, verify clients reconnect
4. **Race conditions**: Simultaneous claims on last item
5. **Performance**: 10+ concurrent users on same receipt