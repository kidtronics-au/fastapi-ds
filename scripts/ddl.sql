CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table for grouping messages into a single help session
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID NOT NULL,
    subject VARCHAR(100),
    topic_context TEXT, -- Optional: store a summary or specific lesson name
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Table for the actual dialogue
CREATE TABLE chat_messages (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    sender_type VARCHAR(20) CHECK (sender_role IN ('student', 'assistant', 'system')),
    
    -- Content stores the text and any embedded media/LaTeX
    content JSONB NOT NULL, 
    
    -- Metadata stores model version, tokens used, or AI reasoning steps
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Feedback for RLHF (Reinforcement Learning from Human Feedback)
    rating SMALLINT CHECK (rating IN (-1, 0, 1)) DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Fast retrieval of a full conversation history
CREATE INDEX idx_messages_session_id ON chat_messages(session_id, created_at ASC);
                                                   
-- GIN Index for high-performance searching inside the JSONB metadata
-- Useful if you want to find all messages that used a specific AI model
CREATE INDEX idx_messages_metadata ON chat_messages USING GIN (metadata);
                                                     
-- GIN Index for the content (if you need to search for specific keywords)
CREATE INDEX idx_messages_content ON chat_messages USING GIN (content);

-- ALTER TABLE chat_messages RENAME COLUMN sender_role TO sender_type;