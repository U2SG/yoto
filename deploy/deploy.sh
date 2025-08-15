#!/bin/bash
set -e  # 任何命令失败则立即退出

# 配置变量
IMAGE_TAG=${1:-latest}  # 接收一个镜像标签作为参数，默认为latest
STACK_NAME="yoto-stack"
SERVICE_NAME="yoto-api"
REGISTRY="docker.io"
REPOSITORY="U2SG/yoto"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查Docker Swarm状态
check_swarm_status() {
    log_info "检查Docker Swarm状态..."
    
    if ! docker info --format '{{.Swarm.LocalNodeState}}' | grep -q "active"; then
        log_error "Docker Swarm未激活，请先初始化Swarm"
        exit 1
    fi
    
    log_info "Docker Swarm状态正常"
}

# 检查服务是否存在
check_service_exists() {
    local service_name="${STACK_NAME}_${SERVICE_NAME}"
    
    if docker service ls --format "{{.Name}}" | grep -q "^${service_name}$"; then
        return 0  # 服务存在
    else
        return 1  # 服务不存在
    fi
}

# 创建服务
create_service() {
    log_info "创建服务 ${SERVICE_NAME}..."
    
    docker service create \
        --name "${STACK_NAME}_${SERVICE_NAME}" \
        --replicas 3 \
        --update-parallelism 1 \
        --update-delay 10s \
        --restart-condition on-failure \
        --env FLASK_ENV=production \
        --env DATABASE_URI="${DATABASE_URI}" \
        --env REDIS_URL="${REDIS_URL}" \
        --network yoto-network \
        --with-registry-auth \
        "${REGISTRY}/${REPOSITORY}:${IMAGE_TAG}"
        
    log_info "服务创建成功"
}

# 更新服务
update_service() {
    log_info "更新服务 ${SERVICE_NAME} 到镜像 ${REGISTRY}/${REPOSITORY}:${IMAGE_TAG}..."
    
    docker service update \
        --image "${REGISTRY}/${REPOSITORY}:${IMAGE_TAG}" \
        --with-registry-auth \
        "${STACK_NAME}_${SERVICE_NAME}"
        
    log_info "服务更新成功"
}

# 健康检查
health_check() {
    log_info "执行健康检查..."
    
    # 等待服务稳定
    sleep 30
    
    # 检查服务状态
    local service_name="${STACK_NAME}_${SERVICE_NAME}"
    local replicas=$(docker service ls --format "{{.Replicas}}" --filter "name=${service_name}")
    
    if [[ "$replicas" == *"3/3"* ]]; then
        log_info "健康检查通过：所有副本运行正常"
        return 0
    else
        log_error "健康检查失败：服务副本状态异常 - $replicas"
        return 1
    fi
}

# 回滚函数
rollback() {
    log_warn "开始回滚到上一个版本..."
    
    # 获取上一个镜像标签
    local previous_tag=$(docker service inspect "${STACK_NAME}_${SERVICE_NAME}" --format '{{.Spec.TaskTemplate.ContainerSpec.Image}}' | cut -d':' -f2)
    
    if [[ -n "$previous_tag" && "$previous_tag" != "$IMAGE_TAG" ]]; then
        docker service update \
            --image "${REGISTRY}/${REPOSITORY}:${previous_tag}" \
            --with-registry-auth \
            "${STACK_NAME}_${SERVICE_NAME}"
            
        log_info "回滚完成，当前版本: $previous_tag"
    else
        log_error "无法获取上一个版本信息"
        exit 1
    fi
}

# 主函数
main() {
    log_info "开始部署流程..."
    log_info "镜像标签: ${IMAGE_TAG}"
    log_info "服务名称: ${SERVICE_NAME}"
    log_info "堆栈名称: ${STACK_NAME}"
    
    # 检查Swarm状态
    check_swarm_status
    
    # 检查服务是否存在
    if check_service_exists; then
        log_info "服务已存在，执行更新..."
        update_service
    else
        log_info "服务不存在，创建新服务..."
        create_service
    fi
    
    # 执行健康检查
    if health_check; then
        log_info "部署成功完成！"
        exit 0
    else
        log_error "部署失败，开始回滚..."
        rollback
        exit 1
    fi
}

# 错误处理
trap 'log_error "部署过程中发生错误，退出码: $?"' ERR

# 执行主函数
main "$@" 