package permission.abac

# 默认策略：拒绝所有访问
default allow = false

# 主要访问控制策略
allow {
    # 检查用户是否有有效会话
    input.user.session_valid == true
    
    # 检查用户是否被禁用
    input.user.disabled != true
    
    # 检查资源是否存在
    input.resource.exists == true
    
    # 检查用户是否有角色权限
    has_role_permission(input.user.roles, input.resource.type, input.action)
    
    # 检查ABAC属性策略
    check_abac_policies(input)
    
    # 检查环境策略
    check_environment_policies(input)
    
    # 检查业务规则
    check_business_rules(input)
    
    # 检查动态策略
    check_dynamic_policies(input)
}

# 角色权限检查
has_role_permission(roles, resource_type, action) {
    role := roles[_]
    role_permissions := get_role_permissions(role)
    permission := role_permissions[_]
    permission.resource_type == resource_type
    permission.action == action
}

# ABAC策略检查
check_abac_policies(input) {
    # 时间策略：检查是否在允许的时间范围内
    check_time_policy(input)
    
    # 位置策略：检查用户位置是否允许
    check_location_policy(input)
    
    # 设备策略：检查设备类型是否允许
    check_device_policy(input)
    
    # 风险策略：检查用户风险等级
    check_risk_policy(input)
    
    # 资源敏感度策略：检查资源敏感度级别
    check_sensitivity_policy(input)
}

# 环境策略检查
check_environment_policies(input) {
    # 检查系统负载
    check_system_load(input)
    
    # 检查网络状态
    check_network_status(input)
    
    # 检查维护模式
    not is_maintenance_mode(input)
    
    # 检查紧急模式
    not is_emergency_mode(input)
}

# 业务规则检查
check_business_rules(input) {
    # 检查用户配额
    check_user_quota(input)
    
    # 检查资源配额
    check_resource_quota(input)
    
    # 检查业务时间窗口
    check_business_hours(input)
    
    # 检查特殊权限
    check_special_permissions(input)
}

# 动态策略检查
check_dynamic_policies(input) {
    # 检查实时风险评分
    check_realtime_risk_score(input)
    
    # 检查行为异常检测
    check_behavior_anomaly(input)
    
    # 检查威胁情报
    check_threat_intelligence(input)
    
    # 检查合规要求
    check_compliance_requirements(input)
}

# 时间策略检查
check_time_policy(input) {
    # 检查是否在工作时间内
    is_work_hours(input.time)
    
    # 检查是否在维护时间外
    not is_maintenance_time(input.time)
    
    # 检查是否在允许的访问时间窗口内
    is_within_access_window(input.time, input.resource.access_window)
}

# 位置策略检查
check_location_policy(input) {
    # 检查用户位置是否在允许的IP范围内
    is_allowed_ip(input.user.ip_address)
    
    # 检查用户位置是否在允许的地理范围内
    is_allowed_location(input.user.location)
    
    # 检查是否在允许的办公地点
    is_allowed_office_location(input.user.location)
    
    # 检查VPN连接状态
    check_vpn_status(input.user)
}

# 设备策略检查
check_device_policy(input) {
    # 检查设备类型是否允许
    is_allowed_device(input.user.device_type)
    
    # 检查设备是否已认证
    input.user.device_authenticated == true
    
    # 检查设备安全状态
    check_device_security(input.user.device_info)
    
    # 检查设备合规性
    check_device_compliance(input.user.device_info)
}

# 风险策略检查
check_risk_policy(input) {
    # 检查用户风险等级
    input.user.risk_level <= input.resource.max_risk_level
    
    # 检查用户行为是否正常
    input.user.behavior_score >= input.resource.min_behavior_score
    
    # 检查用户安全等级
    input.user.security_level >= input.resource.required_security_level
    
    # 检查实时风险评分
    input.user.realtime_risk_score <= input.resource.max_realtime_risk
}

# 资源敏感度策略检查
check_sensitivity_policy(input) {
    # 检查用户安全等级是否满足资源要求
    input.user.security_level >= input.resource.required_security_level
    
    # 检查用户是否有访问敏感资源的权限
    has_sensitive_resource_permission(input.user, input.resource)
    
    # 检查数据分类级别
    check_data_classification(input.user, input.resource)
    
    # 检查数据主权要求
    check_data_sovereignty(input.user, input.resource)
}

# 系统负载检查
check_system_load(input) {
    # 检查CPU使用率
    input.system.cpu_usage < 90
    
    # 检查内存使用率
    input.system.memory_usage < 85
    
    # 检查数据库连接数
    input.system.db_connections < input.system.max_db_connections
    
    # 检查响应时间
    input.system.avg_response_time < 1000  # 毫秒
}

# 网络状态检查
check_network_status(input) {
    # 检查网络延迟
    input.network.latency < 100  # 毫秒
    
    # 检查网络丢包率
    input.network.packet_loss < 0.01  # 1%
    
    # 检查网络带宽
    input.network.bandwidth_usage < 0.8  # 80%
}

# 用户配额检查
check_user_quota(input) {
    # 检查用户API调用次数
    input.user.api_calls_today < input.user.daily_api_limit
    
    # 检查用户数据使用量
    input.user.data_usage < input.user.data_quota
    
    # 检查用户并发会话数
    input.user.active_sessions < input.user.max_concurrent_sessions
}

# 资源配额检查
check_resource_quota(input) {
    # 检查资源访问次数
    input.resource.access_count < input.resource.max_access_count
    
    # 检查资源并发访问数
    input.resource.concurrent_access < input.resource.max_concurrent_access
    
    # 检查资源使用时间
    input.resource.usage_time < input.resource.max_usage_time
}

# 实时风险评分检查
check_realtime_risk_score(input) {
    # 检查用户实时风险评分
    input.user.realtime_risk_score < input.resource.max_realtime_risk
    
    # 检查用户行为异常度
    input.user.behavior_anomaly_score < input.resource.max_anomaly_score
    
    # 检查用户威胁评分
    input.user.threat_score < input.resource.max_threat_score
}

# 行为异常检测
check_behavior_anomaly(input) {
    # 检查用户行为模式是否正常
    input.user.behavior_pattern == "normal"
    
    # 检查用户访问模式是否异常
    not is_abnormal_access_pattern(input.user.access_pattern)
    
    # 检查用户操作频率是否正常
    is_normal_operation_frequency(input.user.operation_frequency)
}

# 威胁情报检查
check_threat_intelligence(input) {
    # 检查用户IP是否在黑名单中
    not is_ip_blacklisted(input.user.ip_address)
    
    # 检查用户是否在威胁情报数据库中
    not is_user_in_threat_intel(input.user.id)
    
    # 检查用户行为是否匹配已知威胁模式
    not matches_threat_pattern(input.user.behavior_pattern)
}

# 合规要求检查
check_compliance_requirements(input) {
    # 检查数据保护法规要求
    check_data_protection_compliance(input)
    
    # 检查行业特定法规要求
    check_industry_compliance(input)
    
    # 检查内部合规要求
    check_internal_compliance(input)
}

# 工作时间内检查
is_work_hours(time) {
    # 周一至周五 9:00-18:00
    time.weekday >= 1
    time.weekday <= 5
    time.hour >= 9
    time.hour < 18
}

# 维护时间检查
is_maintenance_time(time) {
    # 每周日凌晨2:00-4:00为维护时间
    time.weekday == 6  # 周日
    time.hour >= 2
    time.hour < 4
}

# 访问时间窗口检查
is_within_access_window(time, access_window) {
    # 如果没有指定访问窗口，则允许
    access_window == null
}

# 允许的IP检查
is_allowed_ip(ip_address) {
    # 检查是否在允许的IP范围内
    # 这里应该根据实际配置进行检查
    startswith(ip_address, "192.168.")
}

# 允许的位置检查
is_allowed_location(location) {
    # 检查是否在允许的地理位置
    location.country in ["CN", "US", "JP"]
}

# 允许的办公地点检查
is_allowed_office_location(location) {
    # 检查是否在允许的办公地点
    location.office_id in ["HQ", "BRANCH_1", "BRANCH_2"]
}

# VPN状态检查
check_vpn_status(user) {
    # 检查VPN连接状态
    user.vpn_connected == true
    user.vpn_location == user.location.country
}

# 允许的设备检查
is_allowed_device(device_type) {
    # 检查设备类型是否允许
    device_type in ["desktop", "laptop", "mobile", "tablet"]
}

# 设备安全状态检查
check_device_security(device_info) {
    # 检查设备安全状态
    device_info.encryption_enabled == true
    device_info.antivirus_updated == true
    device_info.firewall_enabled == true
}

# 设备合规性检查
check_device_compliance(device_info) {
    # 检查设备是否符合合规要求
    device_info.compliance_score >= 80
    device_info.managed_by_mdm == true
}

# 敏感资源权限检查
has_sensitive_resource_permission(user, resource) {
    # 检查用户是否有访问敏感资源的权限
    user.security_level >= resource.sensitivity_level
    user.has_sensitive_access == true
}

# 数据分类级别检查
check_data_classification(user, resource) {
    # 检查数据分类级别
    user.data_access_level >= resource.data_classification
}

# 数据主权要求检查
check_data_sovereignty(user, resource) {
    # 检查数据主权要求
    user.location.country == resource.data_sovereignty_requirement
}

# 维护模式检查
is_maintenance_mode(input) {
    # 检查系统是否处于维护模式
    input.system.maintenance_mode == true
}

# 紧急模式检查
is_emergency_mode(input) {
    # 检查系统是否处于紧急模式
    input.system.emergency_mode == true
}

# 异常访问模式检查
is_abnormal_access_pattern(access_pattern) {
    # 检查访问模式是否异常
    access_pattern.frequency > 100  # 每分钟超过100次
    access_pattern.time_distribution == "irregular"
}

# 正常操作频率检查
is_normal_operation_frequency(frequency) {
    # 检查操作频率是否正常
    frequency.operations_per_minute < 50
    frequency.operations_per_hour < 1000
}

# IP黑名单检查
is_ip_blacklisted(ip_address) {
    # 检查IP是否在黑名单中
    # 这里应该查询黑名单数据库
    false  # 默认不在黑名单中
}

# 威胁情报检查
is_user_in_threat_intel(user_id) {
    # 检查用户是否在威胁情报数据库中
    # 这里应该查询威胁情报数据库
    false  # 默认不在威胁情报数据库中
}

# 威胁模式匹配检查
matches_threat_pattern(behavior_pattern) {
    # 检查行为是否匹配已知威胁模式
    # 这里应该进行威胁模式匹配
    false  # 默认不匹配威胁模式
}

# 数据保护合规检查
check_data_protection_compliance(input) {
    # 检查数据保护法规要求
    input.compliance.gdpr_compliant == true
    input.compliance.ccpa_compliant == true
}

# 行业合规检查
check_industry_compliance(input) {
    # 检查行业特定法规要求
    input.compliance.sox_compliant == true
    input.compliance.pci_compliant == true
}

# 内部合规检查
check_internal_compliance(input) {
    # 检查内部合规要求
    input.compliance.internal_policy_compliant == true
    input.compliance.audit_requirements_met == true
}

# 获取角色权限（模拟数据）
get_role_permissions(role) {
    # 这里应该从数据库获取角色权限
    # 暂时返回模拟数据
    role == "admin"
    permissions = [
        {"resource_type": "document", "action": "read"},
        {"resource_type": "document", "action": "write"},
        {"resource_type": "user", "action": "manage"}
    ]
}

get_role_permissions(role) {
    role == "user"
    permissions = [
        {"resource_type": "document", "action": "read"}
    ]
}

get_role_permissions(role) {
    role == "manager"
    permissions = [
        {"resource_type": "document", "action": "read"},
        {"resource_type": "document", "action": "write"},
        {"resource_type": "report", "action": "read"}
    ]
}

# 数据访问策略
data_access_policy {
    # 检查数据访问权限
    input.action == "read"
    input.resource.type == "data"
    
    # 检查数据所有者
    input.user.id == input.resource.owner_id
    
    # 检查数据共享权限
    input.resource.shared == true
    input.user.id in input.resource.shared_with
}

# 管理操作策略
admin_operation_policy {
    # 检查管理操作权限
    input.action in ["create", "delete", "update"]
    
    # 检查用户是否有管理权限
    "admin" in input.user.roles
    
    # 检查操作是否在允许的时间范围内
    is_work_hours(input.time)
}

# 紧急访问策略
emergency_access_policy {
    # 检查是否为紧急访问
    input.context.emergency == true
    
    # 检查用户是否有紧急访问权限
    "emergency_access" in input.user.roles
    
    # 检查紧急访问是否已审批
    input.context.emergency_approved == true
}

# 审计日志策略
audit_log_policy {
    # 所有访问都需要记录审计日志
    true
}

# 策略违规处理
policy_violation {
    # 记录策略违规
    input.violation_type = "policy_violation"
    input.violation_details = {
        "user_id": input.user.id,
        "resource_id": input.resource.id,
        "action": input.action,
        "timestamp": input.time,
        "reason": "policy_check_failed"
    }
} 