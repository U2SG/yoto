
# 单用户查询瓶颈分析详细报告

## 发现的瓶颈


## 优化建议


## 性能分析器输出
```
         2368 function calls (2219 primitive calls) in 0.005 seconds

   Ordered by: cumulative time
   List reduced from 456 to 20 due to restriction <20>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
      100    0.000    0.000    0.005    0.000 D:\project\Python\yoto\yoto_backend\performance_tests\..\app\core\permissions.py:720(_optimized_single_user_query_v2)
        1    0.000    0.000    0.005    0.005 D:\project\Python\yoto\yoto_backend\performance_tests\..\app\core\permissions.py:660(_precompute_user_permissions)
        1    0.000    0.000    0.004    0.004 D:\project\Python\yoto\env\Lib\site-packages\sqlalchemy\orm\query.py:2682(all)
        1    0.000    0.000    0.004    0.004 D:\project\Python\yoto\env\Lib\site-packages\sqlalchemy\orm\query.py:2852(_iter)
        1    0.000    0.000    0.004    0.004 D:\project\Python\yoto\env\Lib\site-packages\sqlalchemy\orm\session.py:2305(execute)
        1    0.000    0.000    0.004    0.004 D:\project\Python\yoto\env\Lib\site-packages\sqlalchemy\orm\session.py:2138(_execute_internal)
        1    0.000    0.000    0.003    0.003 D:\project\Python\yoto\env\Lib\site-packages\sqlalchemy\orm\context.py:296(orm_execute_statement)
        1    0.000    0.000    0.003    0.003 D:\project\Python\yoto\env\Lib\site-packages\sqlalchemy\engine\base.py:1371(execute)
        1    0.000    0.000    0.003    0.003 D:\project\Python\yoto\env\Lib\site-packages\sqlalchemy\sql\elements.py:514(_execute_on_connection)
        1    0.000    0.000    0.003    0.003 D:\project\Python\yoto\env\Lib\site-packages\sqlalchemy\engine\base.py:1587(_execute_clauseelement)
        1    0.000    0.000    0.002    0.002 D:\project\Python\yoto\env\Lib\site-packages\sqlalchemy\sql\elements.py:676(_compile_w_cache)
        1    0.000    0.000    0.001    0.001 D:\project\Python\yoto\env\Lib\site-packages\sqlalchemy\engine\base.py:1787(_execute_context)
        1    0.000    0.000    0.001    0.001 D:\project\Python\yoto\env\Lib\site-packages\sqlalchemy\engine\base.py:1846(_exec_single_context)
        1    0.000    0.000    0.001    0.001 D:\project\Python\yoto\env\Lib\site-packages\sqlalchemy\sql\elements.py:314(_compiler)
        1    0.000    0.000    0.001    0.001 D:\project\Python\yoto\env\Lib\site-packages\sqlalchemy\sql\compiler.py:1357(__init__)
        1    0.000    0.000    0.001    0.001 D:\project\Python\yoto\env\Lib\site-packages\sqlalchemy\engine\default.py:942(do_execute)
        1    0.000    0.000    0.001    0.001 D:\project\Python\yoto\env\Lib\site-packages\sqlalchemy\sql\compiler.py:843(__init__)
        1    0.000    0.000    0.001    0.001 D:\project\Python\yoto\env\Lib\site-packages\pymysql\cursors.py:133(execute)
     10/1    0.000    0.000    0.001    0.001 D:\project\Python\yoto\env\Lib\site-packages\sqlalchemy\sql\compiler.py:931(process)
     37/1    0.000    0.000    0.001    0.001 D:\project\Python\yoto\env\Lib\site-packages\sqlalchemy\sql\visitors.py:129(_compiler_dispatch)



```

## 详细性能指标

### cache_access
- l1_cache_hit_time: 0.000000s (avg), 0.000000s (min), 0.000000s (max)
- l1_cache_miss_time: 0.000000s (avg), 0.000000s (min), 0.000000s (max)
- cache_key_generation_time: 0.000002s (avg), 0.000000s (min), 0.000999s (max)
- serialization_time: 0.000018s (avg), 0.000000s (min), 0.001185s (max)
- deserialization_time: 0.000023s (avg), 0.000000s (min), 0.001144s (max)

### permission_aggregation
- role_collection_time: 0.001169s (avg), 0.000000s (min), 0.004104s (max)
- permission_collection_time: 0.002698s (avg), 0.001019s (min), 0.005059s (max)
- scope_filtering_time: 0.001553s (avg), 0.000000s (min), 0.004992s (max)
- set_operations_time: 0.000006s (avg), 0.000000s (min), 0.001310s (max)

### database_query
- join_query_time: 0.003008s (avg), 0.000000s (min), 0.007132s (max)
- subquery_time: 0.003301s (avg), 0.002002s (min), 0.006487s (max)
- distinct_operation_time: 0.001291s (avg), 0.000000s (min), 0.003369s (max)
- filter_operation_time: 0.001397s (avg), 0.000000s (min), 0.004023s (max)
