#!/bin/bash

# Consumer Trend Analysis Agent - Quick Start Script

image_name="consumer-trend-agent"
container_name="trend-agent"
host_port=3000
container_port=8080

echo "🚀 Building Consumer Trend Analysis Agent..."
docker build -t "$image_name" .

echo "🔄 Stopping existing container (if any)..."
docker stop "$container_name" &>/dev/null || true
docker rm "$container_name" &>/dev/null || true

echo "🎯 Starting Trend Analysis Agent..."
docker run -d -p "$host_port":"$container_port" \
    --add-host=host.docker.internal:host-gateway \
    -v "${image_name}-data:/app/backend/data" \
    --env-file .env \
    --name "$container_name" \
    --restart always \
    "$image_name"

echo "🧹 Cleaning up unused images..."
docker image prune -f

echo ""
echo "✅ Trend Analysis Agent is running!"
echo "🌐 Access the web interface at: http://localhost:${host_port}"
echo ""
echo "📝 To view logs: docker logs -f ${container_name}"
echo "🛑 To stop: docker stop ${container_name}"
echo ""
