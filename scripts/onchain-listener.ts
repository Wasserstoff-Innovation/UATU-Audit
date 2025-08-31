#!/usr/bin/env ts-node

/**
 * UatuAudit On-Chain Payment Listener
 * 
 * Listens for OrderPaid events from the AuditOrders contract and
 * forwards them to the backend orchestrator for audit processing.
 * 
 * Features:
 * - WebSocket connection to Base network
 * - Event filtering and parsing
 * - REST API integration with backend
 * - Automatic reconnection and error handling
 * - Logging and monitoring
 */

import 'dotenv/config';
import { WebSocketProvider, Contract, toUtf8String } from 'ethers';
import fetch from 'node-fetch';

// Configuration
const CONFIG = {
    // Base Network Configuration
    BASE_WS: process.env.BASE_WS!,
    ORDERS_ADDRESS: process.env.ORDERS_ADDRESS!,
    
    // Backend Integration
    ORCH_URL: process.env.ORCH_URL!,
    ORCH_TOKEN: process.env.ORCH_TOKEN!,
    
    // Monitoring
    LOG_LEVEL: process.env.LOG_LEVEL || 'info',
    HEARTBEAT_INTERVAL: parseInt(process.env.HEARTBEAT_INTERVAL || '30000'), // 30s
    MAX_RECONNECT_ATTEMPTS: parseInt(process.env.MAX_RECONNECT_ATTEMPTS || '10'),
    RECONNECT_DELAY: parseInt(process.env.RECONNECT_DELAY || '5000'), // 5s
};

// Contract ABI (minimal for events)
const CONTRACT_ABI = [
    {
        "anonymous": false,
        "inputs": [
            {"indexed": true, "name": "orderId", "type": "bytes32"},
            {"indexed": true, "name": "payer", "type": "address"},
            {"indexed": false, "name": "repo", "type": "string"},
            {"indexed": false, "name": "commit", "type": "string"},
            {"indexed": false, "name": "amount", "type": "uint256"},
            {"indexed": false, "name": "token", "type": "address"},
            {"indexed": false, "name": "chainId", "type": "uint256"}
        ],
        "name": "OrderPaid",
        "type": "event"
    }
];

// State management
let provider: WebSocketProvider;
let contract: Contract;
let reconnectAttempts = 0;
let isConnected = false;
let heartbeatInterval: NodeJS.Timeout;

// Logging
enum LogLevel {
    DEBUG = 0,
    INFO = 1,
    WARN = 2,
    ERROR = 3
}

const currentLogLevel = LogLevel[CONFIG.LOG_LEVEL.toUpperCase() as keyof typeof LogLevel] || LogLevel.INFO;

function log(level: LogLevel, message: string, data?: any) {
    if (level >= currentLogLevel) {
        const timestamp = new Date().toISOString();
        const levelStr = LogLevel[level];
        const prefix = `[${timestamp}] [${levelStr}]`;
        
        if (data) {
            console.log(`${prefix} ${message}`, data);
        } else {
            console.log(`${prefix} ${message}`);
        }
    }
}

// Connection management
async function connect() {
    try {
        log(LogLevel.INFO, `Connecting to Base network via ${CONFIG.BASE_WS}...`);
        
        provider = new WebSocketProvider(CONFIG.BASE_WS);
        contract = new Contract(CONFIG.ORDERS_ADDRESS, CONTRACT_ABI, provider);
        
        // Test connection
        const network = await provider.getNetwork();
        log(LogLevel.INFO, `Connected to network: ${network.name} (chainId: ${network.chainId})`);
        
        // Verify contract exists
        const code = await provider.getCode(CONFIG.ORDERS_ADDRESS);
        if (code === '0x') {
            throw new Error(`No contract found at ${CONFIG.ORDERS_ADDRESS}`);
        }
        
        log(LogLevel.INFO, `Contract verified at ${CONFIG.ORDERS_ADDRESS}`);
        
        // Setup event listeners
        setupEventListeners();
        
        // Setup connection monitoring
        setupConnectionMonitoring();
        
        // Start heartbeat
        startHeartbeat();
        
        isConnected = true;
        reconnectAttempts = 0;
        
        log(LogLevel.INFO, 'On-chain listener started successfully');
        
    } catch (error) {
        log(LogLevel.ERROR, 'Connection failed:', error);
        await handleReconnect();
    }
}

function setupEventListeners() {
    // Listen for OrderPaid events
    contract.on("OrderPaid", async (orderId, payer, repo, commit, amount, token, chainId, event) => {
        try {
            log(LogLevel.INFO, 'OrderPaid event received:', {
                orderId: orderId.toString(),
                payer: payer.toString(),
                repo: repo.toString(),
                commit: commit.toString(),
                amount: amount.toString(),
                token: token.toString(),
                chainId: chainId.toString(),
                blockNumber: event.log.blockNumber,
                transactionHash: event.log.transactionHash
            });
            
            // Forward to backend orchestrator
            await forwardToBackend({
                orderId: orderId.toString(),
                payer: payer.toString(),
                repo: repo.toString(),
                commit: commit.toString(),
                amount: amount.toString(),
                token: token.toString(),
                chainId: chainId.toString(),
                blockNumber: event.log.blockNumber,
                transactionHash: event.log.transactionHash,
                timestamp: Date.now()
            });
            
        } catch (error) {
            log(LogLevel.ERROR, 'Error processing OrderPaid event:', error);
        }
    });
    
    // Listen for connection events
    provider.on('connect', () => {
        log(LogLevel.INFO, 'WebSocket connected');
        isConnected = true;
    });
    
    provider.on('disconnect', () => {
        log(LogLevel.WARN, 'WebSocket disconnected');
        isConnected = false;
        handleDisconnect();
    });
    
    provider.on('error', (error) => {
        log(LogLevel.ERROR, 'WebSocket error:', error);
        handleDisconnect();
    });
}

function setupConnectionMonitoring() {
    // Monitor connection health
    setInterval(async () => {
        if (!isConnected) return;
        
        try {
            const blockNumber = await provider.getBlockNumber();
            log(LogLevel.DEBUG, `Connection healthy, latest block: ${blockNumber}`);
        } catch (error) {
            log(LogLevel.WARN, 'Connection health check failed:', error);
            handleDisconnect();
        }
    }, 60000); // Check every minute
}

function startHeartbeat() {
    heartbeatInterval = setInterval(() => {
        if (isConnected) {
            log(LogLevel.DEBUG, 'Heartbeat: Listener is running');
        }
    }, CONFIG.HEARTBEAT_INTERVAL);
}

async function forwardToBackend(orderData: any) {
    try {
        log(LogLevel.INFO, 'Forwarding order to backend...');
        
        const response = await fetch(`${CONFIG.ORCH_URL}/api/orders/onchain`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${CONFIG.ORCH_TOKEN}`,
                'User-Agent': 'UatuAudit-OnChainListener/1.0'
            },
            body: JSON.stringify(orderData),
            timeout: 30000 // 30 second timeout
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Backend responded with ${response.status}: ${errorText}`);
        }
        
        const result = await response.json();
        log(LogLevel.INFO, '✓ Order queued successfully:', result);
        
    } catch (error) {
        log(LogLevel.ERROR, 'Failed to forward order to backend:', error);
        
        // In production, you might want to:
        // 1. Retry with exponential backoff
        // 2. Store failed orders in a queue
        // 3. Alert operators
        // 4. Implement dead letter queue
        
        throw error;
    }
}

async function handleReconnect() {
    if (reconnectAttempts >= CONFIG.MAX_RECONNECT_ATTEMPTS) {
        log(LogLevel.ERROR, `Max reconnection attempts (${CONFIG.MAX_RECONNECT_ATTEMPTS}) reached. Exiting.`);
        process.exit(1);
    }
    
    reconnectAttempts++;
    const delay = CONFIG.RECONNECT_DELAY * Math.pow(2, reconnectAttempts - 1); // Exponential backoff
    
    log(LogLevel.WARN, `Reconnection attempt ${reconnectAttempts}/${CONFIG.MAX_RECONNECT_ATTEMPTS} in ${delay}ms...`);
    
    setTimeout(async () => {
        try {
            await connect();
        } catch (error) {
            log(LogLevel.ERROR, 'Reconnection failed:', error);
            await handleReconnect();
        }
    }, delay);
}

function handleDisconnect() {
    isConnected = false;
    log(LogLevel.WARN, 'Handling disconnection...');
    
    // Clear heartbeat
    if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
    }
    
    // Attempt reconnection
    handleReconnect();
}

// Graceful shutdown
async function shutdown(signal: string) {
    log(LogLevel.INFO, `Received ${signal}, shutting down gracefully...`);
    
    // Clear intervals
    if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
    }
    
    // Close provider connection
    if (provider) {
        await provider.destroy();
    }
    
    log(LogLevel.INFO, 'Shutdown complete');
    process.exit(0);
}

// Process management
process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
process.on('uncaughtException', (error) => {
    log(LogLevel.ERROR, 'Uncaught exception:', error);
    process.exit(1);
});
process.on('unhandledRejection', (reason, promise) => {
    log(LogLevel.ERROR, 'Unhandled rejection at:', promise, 'reason:', reason);
    process.exit(1);
});

// Main execution
async function main() {
    log(LogLevel.INFO, 'Starting UatuAudit On-Chain Listener...');
    
    // Validate configuration
    const requiredEnvVars = ['BASE_WS', 'ORDERS_ADDRESS', 'ORCH_URL', 'ORCH_TOKEN'];
    const missingVars = requiredEnvVars.filter(varName => !process.env[varName]);
    
    if (missingVars.length > 0) {
        log(LogLevel.ERROR, `Missing required environment variables: ${missingVars.join(', ')}`);
        log(LogLevel.INFO, 'Please check your .env file or environment configuration');
        process.exit(1);
    }
    
    log(LogLevel.INFO, 'Configuration validated');
    
    // Connect to network
    await connect();
    
    // Keep process alive
    log(LogLevel.INFO, 'Listener is running. Press Ctrl+C to stop.');
}

// Start the listener
if (require.main === module) {
    main().catch((error) => {
        log(LogLevel.ERROR, 'Fatal error in main:', error);
        process.exit(1);
    });
}

export { connect, forwardToBackend, shutdown };
