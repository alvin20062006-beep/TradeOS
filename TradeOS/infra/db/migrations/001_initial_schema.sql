-- AI Trading Tool - Initial Database Schema
-- PostgreSQL compatible (SQLite for dev, PostgreSQL for prod)
-- Migration: 001_initial_schema

-- Enable UUID extension (PostgreSQL)
-- For SQLite this is auto, for PostgreSQL we need:
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ================================================================
-- DECISIONS
-- ================================================================
CREATE TABLE decisions (
    id TEXT PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('long', 'short', 'flat')),
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    regime TEXT NOT NULL CHECK (regime IN ('trending_up', 'trending_down', 'ranging', 'volatile', 'unknown')),
    entry_permission BOOLEAN NOT NULL DEFAULT TRUE,
    no_trade_reason TEXT,
    max_position_pct REAL NOT NULL DEFAULT 0.1,
    suggested_quantity REAL,
    execution_style TEXT NOT NULL DEFAULT 'market',
    limit_price REAL,
    stop_price REAL,
    stop_logic JSONB,
    take_profit REAL,
    engine_signals JSONB NOT NULL DEFAULT '{}',
    consensus_score REAL NOT NULL DEFAULT 0.5,
    reasoning TEXT,
    key_factors JSONB DEFAULT '[]',
    version TEXT NOT NULL DEFAULT '1.0.0',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_decisions_symbol ON decisions(symbol);
CREATE INDEX idx_decisions_timestamp ON decisions(timestamp DESC);
CREATE INDEX idx_decisions_direction ON decisions(direction);
CREATE INDEX idx_decisions_regime ON decisions(regime);

-- ================================================================
-- EXECUTIONS (Orders)
-- ================================================================
CREATE TABLE orders (
    id TEXT PRIMARY KEY,
    decision_id TEXT REFERENCES decisions(id),
    symbol TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    
    -- Order spec
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    order_type TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL,
    stop_price REAL,
    
    -- Status
    status TEXT NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'submitted', 'partial_filled', 'filled', 'cancelled', 'rejected', 'expired')),
    submitted_at TIMESTAMPTZ,
    filled_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    
    -- Fill tracking
    filled_quantity REAL NOT NULL DEFAULT 0,
    avg_fill_price REAL,
    
    -- Execution quality
    slippage_bps REAL,
    execution_quality TEXT CHECK (execution_quality IN ('excellent', 'good', 'fair', 'poor', 'failed')),
    
    -- Exchange
    exchange_order_id TEXT,
    exchange TEXT,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_orders_decision ON orders(decision_id);
CREATE INDEX idx_orders_symbol ON orders(symbol);
CREATE INDEX idx_orders_timestamp ON orders(timestamp DESC);
CREATE INDEX idx_orders_status ON orders(status);

-- ================================================================
-- FILLS
-- ================================================================
CREATE TABLE fills (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(id),
    timestamp TIMESTAMPTZ NOT NULL,
    price REAL NOT NULL,
    quantity REAL NOT NULL,
    side TEXT NOT NULL,
    
    -- Fees
    commission REAL NOT NULL DEFAULT 0,
    commission_currency TEXT NOT NULL DEFAULT 'USD',
    
    -- Quality
    is_maker BOOLEAN,
    liquidity_type TEXT,
    
    exchange_fill_id TEXT,
    venue TEXT,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_fills_order ON fills(order_id);
CREATE INDEX idx_fills_symbol ON fills(timestamp DESC);

-- ================================================================
-- RISK EVENTS
-- ================================================================
CREATE TABLE risk_events (
    id TEXT PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    event_type TEXT NOT NULL,
    symbol TEXT,
    
    -- Details
    description TEXT NOT NULL,
    triggered_value REAL NOT NULL,
    threshold_value REAL NOT NULL,
    
    -- Action
    action_taken TEXT NOT NULL,
    position_closed BOOLEAN NOT NULL DEFAULT FALSE,
    order_cancelled BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Context
    decision_id TEXT REFERENCES decisions(id),
    
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_risk_events_timestamp ON risk_events(timestamp DESC);
CREATE INDEX idx_risk_events_type ON risk_events(event_type);

-- ================================================================
-- AUDIT LOG
-- ================================================================
CREATE TABLE audit_log (
    id TEXT PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    
    -- Classification
    record_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    
    -- Who/Where
    source TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'system',
    
    -- What
    action TEXT NOT NULL,
    before_state JSONB,
    after_state JSONB,
    reason TEXT,
    
    -- Correlation
    correlation_id TEXT,
    
    metadata JSONB DEFAULT '{}',
    checksum TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_timestamp ON audit_log(timestamp DESC);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_record_type ON audit_log(record_type);
CREATE INDEX idx_audit_correlation ON audit_log(correlation_id);

-- ================================================================
-- MODEL REGISTRY
-- ================================================================
CREATE TABLE model_registry (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    model_type TEXT NOT NULL,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'system',
    
    -- Training
    training_start TIMESTAMPTZ,
    training_end TIMESTAMPTZ,
    training_samples INTEGER DEFAULT 0,
    
    -- Performance
    metrics JSONB DEFAULT '{}',
    
    -- Status
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    is_production BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Lineage
    parent_model_id TEXT REFERENCES model_registry(id),
    experiment_id TEXT,
    
    config JSONB DEFAULT '{}',
    artifacts_path TEXT,
    
    metadata JSONB DEFAULT '{}'
);

CREATE UNIQUE INDEX idx_model_registry_name_version ON model_registry(name, version);
CREATE INDEX idx_model_registry_active ON model_registry(is_active, is_production);

-- ================================================================
-- EXPERIMENTS
-- ================================================================
CREATE TABLE experiments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running' 
        CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    
    config JSONB DEFAULT '{}',
    results JSONB DEFAULT '{}',
    metrics JSONB DEFAULT '{}',
    
    model_ids JSONB DEFAULT '[]',
    dataset_version TEXT,
    
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_experiments_status ON experiments(status);
CREATE INDEX idx_experiments_started ON experiments(started_at DESC);

-- ================================================================
-- LIVE FEEDBACK
-- ================================================================
CREATE TABLE live_feedback (
    id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL REFERENCES decisions(id),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- P&L
    pnl REAL,
    pnl_pct REAL,
    
    -- Outcome
    holding_period_seconds INTEGER,
    outcome TEXT CHECK (outcome IN ('win', 'loss', 'breakeven', 'pending')),
    
    -- Actual vs predicted
    actual_return REAL,
    predicted_return REAL,
    
    -- Analysis
    key_lessons TEXT,
    notes TEXT,
    
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_feedback_decision ON live_feedback(decision_id);
CREATE INDEX idx_feedback_outcome ON live_feedback(outcome);
CREATE INDEX idx_feedback_timestamp ON live_feedback(timestamp DESC);

-- ================================================================
-- POSITIONS (snapshot tracking)
-- ================================================================
CREATE TABLE position_snapshots (
    id TEXT PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol TEXT NOT NULL,
    
    quantity REAL NOT NULL DEFAULT 0,
    side TEXT CHECK (side IN ('long', 'short', 'flat')),
    avg_entry_price REAL DEFAULT 0,
    
    unrealized_pnl REAL DEFAULT 0,
    realized_pnl REAL DEFAULT 0,
    pnl_pct REAL DEFAULT 0,
    
    exposure_pct REAL DEFAULT 0,
    margin_used REAL DEFAULT 0,
    
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_position_snapshots_symbol ON position_snapshots(symbol);
CREATE INDEX idx_position_snapshots_timestamp ON position_snapshots(timestamp DESC);

-- ================================================================
-- PORTFOLIO (snapshot tracking)
-- ================================================================
CREATE TABLE portfolio_snapshots (
    id TEXT PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    total_equity REAL NOT NULL,
    cash REAL NOT NULL,
    margin_used REAL DEFAULT 0,
    
    daily_pnl REAL DEFAULT 0,
    daily_pnl_pct REAL DEFAULT 0,
    total_pnl REAL DEFAULT 0,
    total_pnl_pct REAL DEFAULT 0,
    
    current_drawdown REAL DEFAULT 0,
    peak_equity REAL NOT NULL,
    
    leverage REAL DEFAULT 1.0,
    beta_exposure REAL DEFAULT 0,
    
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_portfolio_snapshots_timestamp ON portfolio_snapshots(timestamp DESC);

-- ================================================================
-- SYSTEM EVENTS (deployment, config changes, etc.)
-- ================================================================
CREATE TABLE system_events (
    id TEXT PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type TEXT NOT NULL,
    
    component TEXT NOT NULL,
    version TEXT,
    
    description TEXT,
    config_snapshot JSONB,
    
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_system_events_timestamp ON system_events(timestamp DESC);
CREATE INDEX idx_system_events_type ON system_events(event_type);

-- ================================================================
-- FUNCTIONS & TRIGGERS
-- ================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate daily P&L from positions
CREATE OR REPLACE FUNCTION calculate_daily_pnl(symbol TEXT, trade_date DATE)
RETURNS REAL AS $$
DECLARE
    daily_pnl REAL := 0;
BEGIN
    SELECT COALESCE(SUM(
        CASE 
            WHEN side = 'long' THEN (close - avg_entry_price) * quantity
            WHEN side = 'short' THEN (avg_entry_price - close) * quantity
            ELSE 0
        END
    ), 0)
    INTO daily_pnl
    FROM position_snapshots
    WHERE symbol = symbol
      AND DATE(timestamp) = trade_date;
    
    RETURN daily_pnl;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-create audit log on decision creation
-- Note: This should be handled in application layer for flexibility
