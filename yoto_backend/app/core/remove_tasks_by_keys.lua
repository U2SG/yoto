-- KEYS[1]: a set of cache_keys to find and remove
-- ARGV[1]: the name of the ZSET (delayed_invalidation_queue)

local cache_keys_to_remove_set = {}
for i, key in ipairs(redis.call('SMEMBERS', KEYS[1])) do
    cache_keys_to_remove_set[key] = true
end

if next(cache_keys_to_remove_set) == nil then
    return 0
end

local tasks_to_remove_from_zset = {}
local removed_count = 0
local cursor = '0'

repeat
    local result = redis.call('ZSCAN', ARGV[1], cursor, 'COUNT', 1000)
    cursor = result[1]
    local members = result[2]

    for i=1, #members, 2 do
        local task_json = members[i]
        local task = cjson.decode(task_json)
        if task and task.cache_key and cache_keys_to_remove_set[task.cache_key] then
            table.insert(tasks_to_remove_from_zset, task_json)
        end
    end
until cursor == '0'

if #tasks_to_remove_from_zset > 0 then
    -- Unpack is needed for redis.call
    removed_count = redis.call('ZREM', ARGV[1], unpack(tasks_to_remove_from_zset))
end

return removed_count