## Step-by-Step Optimization Architecture

### Phase 1: Remove Repository Anti-Pattern (Week 1)

**Goal**: Eliminate repositories and use Django ORM properly

1. **Move optimized queries directly to services**
   - Remove `ReceiptRepository` and `ClaimRepository` classes
   - Implement proper Django ORM queries in service methods
   - Use bulk operations, select_related, prefetch_related correctly

2. **Fix the N+1 query in participant totals**:
   ```python
   # BEFORE (21 queries for 20 claims):
   def get_participant_totals(self, receipt_id: str) -> Dict[str, Decimal]:
       claims = Claim.objects.filter(line_item__receipt_id=receipt_id).select_related('line_item')
       for claim in claims:
           total += claim.get_share_amount()  # N+1 query!

   # AFTER (1 query):
   def get_participant_totals(self, receipt_id: str) -> Dict[str, Decimal]:
       return Claim.objects.filter(
           line_item__receipt_id=receipt_id
       ).values('claimer_name').annotate(
           total=Sum(
               F('quantity_claimed') * (
                   F('line_item__total_price') + 
                   F('line_item__prorated_tax') + 
                   F('line_item__prorated_tip')
               ),
               output_field=DecimalField()
           )
       )
   ```

3. **Optimize receipt viewing query**:
   ```python
   # Single query with all needed data
   def get_receipt_for_viewing(self, receipt_id: str) -> Dict:
       receipt = Receipt.objects.select_related().prefetch_related(
           'items',
           'viewers',
           Prefetch(
               'items__claims',
               queryset=Claim.objects.select_related().order_by('claimed_at')
           )
       ).get(id=receipt_id)
   ```

### Phase 2: Fix Write Amplification (Week 1)

**Goal**: Reduce database writes by 80%

1. **Implement bulk item creation**:
   ```python
   def create_receipt_with_items(self, data: Dict) -> Receipt:
       receipt = Receipt.objects.create(**receipt_data)
       
       # Calculate all prorations in memory
       items = []
       for item_data in items_data:
           item = LineItem(receipt=receipt, **item_data)
           item.calculate_prorations()  # No DB access needed
           items.append(item)
       
       # Single bulk insert
       LineItem.objects.bulk_create(items)
       return receipt
   ```

2. **Use bulk_update for claim operations**:
   ```python
   def finalize_claims_bulk(self, receipt_id: str, claims_data: List[Dict]) -> None:
       claims_to_create = []
       for claim_data in claims_data:
           if claim_data['quantity'] > 0:
               claims_to_create.append(Claim(
                   line_item_id=claim_data['line_item_id'],
                   claimer_name=claim_data['claimer_name'],
                   quantity_claimed=claim_data['quantity'],
                   session_id=claim_data['session_id'],
                   is_finalized=True,
                   finalized_at=timezone.now()
               ))
       
       Claim.objects.bulk_create(claims_to_create)
   ```

### Phase 3: Add Critical Database Indexes (Immediate)

**Goal**: 10x improvement in filtered queries

1. **Create database migration**:
   ```python
   # 0007_add_performance_indexes.py
   operations = [
       migrations.RunSQL(
           "CREATE INDEX CONCURRENTLY idx_claim_session_id ON receipts_claim(session_id);",
           reverse_sql="DROP INDEX IF EXISTS idx_claim_session_id;"
       ),
       migrations.RunSQL(
           "CREATE INDEX CONCURRENTLY idx_claim_claimer_name ON receipts_claim(claimer_name);",
           reverse_sql="DROP INDEX IF EXISTS idx_claim_claimer_name;"
       ),
       migrations.RunSQL(
           "CREATE INDEX CONCURRENTLY idx_claim_receipt_session ON receipts_claim(line_item_id, session_id);",
           reverse_sql="DROP INDEX IF EXISTS idx_claim_receipt_session;"
       ),
       migrations.RunSQL(
           "CREATE INDEX CONCURRENTLY idx_activeviewer_session_id ON receipts_activeviewer(session_id);",
           reverse_sql="DROP INDEX IF EXISTS idx_activeviewer_session_id;"
       ),
   ]
   ```

2. **Add model index definitions**:
   ```python
   class Claim(models.Model):
       # ... existing fields ...
       
       class Meta:
           indexes = [
               models.Index(fields=['session_id']),
               models.Index(fields=['claimer_name']),
               models.Index(fields=['line_item', 'session_id']),
           ]
   ```

### Phase 4: Implement Strategic Caching (Week 2)

**Goal**: Eliminate redundant calculations

1. **Cache finalized receipt totals**:
   ```python
   def get_participant_totals_cached(self, receipt_id: str) -> Dict[str, Decimal]:
       cache_key = f"participant_totals:{receipt_id}"
       
       # Check if receipt is finalized
       if Receipt.objects.filter(id=receipt_id, is_finalized=True).exists():
           cached = cache.get(cache_key)
           if cached:
               return cached
       
       totals = self.get_participant_totals(receipt_id)
       
       # Cache finalized receipts for 1 hour
       if Receipt.objects.filter(id=receipt_id, is_finalized=True).exists():
           cache.set(cache_key, totals, 3600)
       
       return totals
   ```

2. **Cache receipt view data**:
   ```python
   def get_receipt_view_data_cached(self, receipt_id: str) -> Dict:
       # Cache the expensive calculation parts
       cache_key = f"receipt_view:{receipt_id}"
       
       # Only cache if receipt is finalized and no recent claims
       receipt = Receipt.objects.get(id=receipt_id)
       if receipt.is_finalized:
           cached = cache.get(cache_key)
           if cached:
               return cached
       
       data = self.get_receipt_for_viewing(receipt_id)
       
       if receipt.is_finalized:
           cache.set(cache_key, data, 1800)  # 30 minutes
       
       return data
   ```

### Phase 5: Add Query Monitoring (Week 2)

**Goal**: Prevent future performance regressions

1. **Add django-debug-toolbar in development**:
   ```python
   # settings.py
   if DEBUG:
       INSTALLED_APPS += ['debug_toolbar']
       MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
   ```

2. **Implement query counting middleware**:
   ```python
   class QueryCountMiddleware:
       def __init__(self, get_response):
           self.get_response = get_response
       
       def __call__(self, request):
           from django.db import connection
           
           queries_before = len(connection.queries)
           response = self.get_response(request)
           queries_after = len(connection.queries)
           
           query_count = queries_after - queries_before
           
           if query_count > 10:  # Alert threshold
               logger.warning(f"High query count: {query_count} for {request.path}")
           
           response['X-Query-Count'] = str(query_count)
           return response
   ```

3. **Add performance logging**:
   ```python
   import time
   from django.db import connection
   
   def log_query_performance(func):
       def wrapper(*args, **kwargs):
           start_time = time.time()
           start_queries = len(connection.queries)
           
           result = func(*args, **kwargs)
           
           end_time = time.time()
           end_queries = len(connection.queries)
           
           duration = (end_time - start_time) * 1000  # ms
           query_count = end_queries - start_queries
           
           if duration > 100 or query_count > 5:
               logger.info(f"{func.__name__}: {duration:.2f}ms, {query_count} queries")
           
           return result
       return wrapper
   ```

### Phase 6: Optimize Specific Query Patterns (Week 3)

**Goal**: Address remaining hotspots

1. **Optimize claim availability checks**:
   ```python
   def get_items_with_availability(self, receipt_id: str, session_id: str) -> List[Dict]:
       # Single query with all availability calculations
       items = LineItem.objects.filter(
           receipt_id=receipt_id
       ).annotate(
           total_claimed=Coalesce(Sum('claims__quantity_claimed'), 0),
           claimed_by_others=Coalesce(
               Sum('claims__quantity_claimed', 
                   filter=~Q(claims__session_id=session_id)), 0
           ),
           available_for_session=F('quantity') - F('claimed_by_others'),
           current_user_claimed=Coalesce(
               Sum('claims__quantity_claimed',
                   filter=Q(claims__session_id=session_id)), 0
           )
       ).select_related('receipt')
       
       return list(items)
   ```

2. **Optimize finalization validation**:
   ```python
   def validate_receipt_balance_fast(self, receipt_id: str) -> Tuple[bool, Dict]:
       # Single query validation
       receipt_data = Receipt.objects.filter(id=receipt_id).aggregate(
           subtotal=F('subtotal'),
           tax=F('tax'),
           tip=F('tip'),
           total=F('total'),
           items_total=Sum('items__total_price')
       )
       
       # Fast validation without additional queries
       is_valid = (
           receipt_data['items_total'] == receipt_data['subtotal'] and
           receipt_data['subtotal'] + receipt_data['tax'] + receipt_data['tip'] == receipt_data['total']
       )
       
       return is_valid, receipt_data
   ```

IMPORTANT: Start by REMOVING REPOSITORY CLASSES AND MOVE QUERIES TO SERVICES DIRECTLY. Then optimize starting with phase 1.2..
