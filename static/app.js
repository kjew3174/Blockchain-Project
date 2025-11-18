const API_BASE = '';

let autoRefreshInterval = null;
let isAutoRefreshing = false;

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    refreshAll();
    setInterval(refreshStatus, 5000); // 5초마다 상태 업데이트
});

// 전체 새로고침
function refreshAll() {
    refreshStatus();
    refreshChain();
}

// 상태 정보 새로고침
async function refreshStatus() {
    try {
        const [nodesRes, chainRes, statusRes] = await Promise.all([
            fetch(`${API_BASE}/get_nodes`),
            fetch(`${API_BASE}/get_chain`),
            fetch(`${API_BASE}/api/status`)
        ]);

        if (nodesRes.ok) {
            const nodesData = await nodesRes.json();
            updateNodeStatus(nodesData.nodes || []);
        }

        if (chainRes.ok) {
            const chainData = await chainRes.json();
            updateChainStatus(chainData);
        }

        if (statusRes.ok) {
            const statusData = await statusRes.json();
            document.getElementById('pending-tx').textContent = statusData.pending_transactions || 0;
            document.getElementById('pending-tx-count').textContent = statusData.pending_transactions || 0;
        }
    } catch (error) {
        console.error('상태 새로고침 실패:', error);
    }
}

// 노드 상태 업데이트
function updateNodeStatus(nodes) {
    const nodeCount = nodes.length;
    document.getElementById('node-count').textContent = `연결된 노드: ${nodeCount}`;
    document.getElementById('connected-nodes').textContent = nodeCount;
    
    const nodesUl = document.getElementById('nodes-ul');
    nodesUl.innerHTML = '';
    
    if (nodes.length === 0) {
        nodesUl.innerHTML = '<li style="color: #999;">연결된 노드가 없습니다</li>';
    } else {
        nodes.forEach(node => {
            const li = document.createElement('li');
            li.textContent = node;
            nodesUl.appendChild(li);
        });
    }
}

// 체인 상태 업데이트
function updateChainStatus(chainData) {
    const chainLength = chainData.length || 0;
    document.getElementById('chain-length').textContent = chainLength;
}

// 트랜잭션 추가
async function addTransaction(event) {
    event.preventDefault();
    
    const sender = document.getElementById('sender').value;
    const receiver = document.getElementById('receiver').value;
    const amount = parseFloat(document.getElementById('amount').value);
    
    const messageDiv = document.getElementById('tx-message');
    messageDiv.className = 'message';
    messageDiv.textContent = '처리 중...';
    messageDiv.style.display = 'block';
    
    try {
        const response = await fetch(`${API_BASE}/add_transaction`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ sender, receiver, amount })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            messageDiv.className = 'message success';
            messageDiv.textContent = `✅ 트랜잭션이 추가되었습니다: ${sender} → ${receiver} (${amount})`;
            
            // 폼 초기화
            document.getElementById('tx-form').reset();
            
            // 상태 새로고침
            setTimeout(refreshStatus, 1000);
        } else {
            messageDiv.className = 'message error';
            messageDiv.textContent = `❌ 오류: ${data.message || '트랜잭션 추가 실패'}`;
        }
    } catch (error) {
        messageDiv.className = 'message error';
        messageDiv.textContent = `❌ 네트워크 오류: ${error.message}`;
    }
}

// 블록 채굴
async function mineBlock() {
    const btn = document.getElementById('mine-btn');
    const messageDiv = document.getElementById('mine-message');
    
    btn.disabled = true;
    messageDiv.className = 'message info';
    messageDiv.textContent = '⛏️ 블록 채굴 중...';
    messageDiv.style.display = 'block';
    
    try {
        const response = await fetch(`${API_BASE}/mine`);
        const data = await response.json();
        
        if (response.ok) {
            messageDiv.className = 'message success';
            messageDiv.textContent = `✅ ${data.message || '블록이 채굴되었습니다!'}`;
            
            // 상태 및 체인 새로고침
            setTimeout(() => {
                refreshAll();
            }, 1000);
        } else {
            messageDiv.className = 'message error';
            messageDiv.textContent = `❌ 오류: ${data.message || '블록 채굴 실패'}`;
        }
    } catch (error) {
        messageDiv.className = 'message error';
        messageDiv.textContent = `❌ 네트워크 오류: ${error.message}`;
    } finally {
        btn.disabled = false;
    }
}

// 체인 새로고침
async function refreshChain() {
    const container = document.getElementById('chain-container');
    container.innerHTML = '<div class="loading">로딩 중...</div>';
    
    try {
        const response = await fetch(`${API_BASE}/get_chain`);
        const data = await response.json();
        
        if (response.ok && data.chain) {
            displayChain(data.chain);
        } else {
            container.innerHTML = '<div class="empty">체인 정보를 가져올 수 없습니다</div>';
        }
    } catch (error) {
        container.innerHTML = `<div class="empty">오류: ${error.message}</div>`;
    }
}

// 체인 표시
function displayChain(chain) {
    const container = document.getElementById('chain-container');
    
    if (chain.length === 0) {
        container.innerHTML = '<div class="empty">블록이 없습니다. 첫 번째 블록을 채굴하세요!</div>';
        return;
    }
    
    container.innerHTML = '';
    
    // 역순으로 표시 (최신 블록이 위에)
    [...chain].reverse().forEach(block => {
        const blockDiv = document.createElement('div');
        blockDiv.className = 'block';
        
        const timestamp = new Date(block.timestamp * 1000).toLocaleString('ko-KR');
        
        blockDiv.innerHTML = `
            <div class="block-header">
                <div class="block-index">블록 #${block.index}</div>
                <div class="block-hash">${block.hash}</div>
            </div>
            <div class="block-details">
                <div class="block-detail">
                    <label>이전 해시:</label>
                    <div class="value">${block.previous_hash}</div>
                </div>
                <div class="block-detail">
                    <label>타임스탬프:</label>
                    <div class="value">${timestamp}</div>
                </div>
                <div class="block-detail">
                    <label>Nonce:</label>
                    <div class="value">${block.nonce}</div>
                </div>
            </div>
            ${block.transactions && block.transactions.length > 0 ? `
                <div class="transactions">
                    <h4>트랜잭션 (${block.transactions.length}개)</h4>
                    ${block.transactions.map(tx => `
                        <div class="transaction">
                            <div class="transaction-item">
                                <strong>보낸이:</strong> ${tx.sender || 'N/A'}
                            </div>
                            <div class="transaction-item">
                                <strong>받는이:</strong> ${tx.receiver || 'N/A'}
                            </div>
                            <div class="transaction-item">
                                <strong>금액:</strong> ${tx.amount || 0}
                            </div>
                        </div>
                    `).join('')}
                </div>
            ` : '<div class="transactions"><p style="color: #999;">트랜잭션 없음</p></div>'}
        `;
        
        container.appendChild(blockDiv);
    });
}

// 전체 동기화
async function syncAll() {
    const messageDiv = document.getElementById('tx-message');
    messageDiv.className = 'message info';
    messageDiv.textContent = '🔄 동기화 중...';
    messageDiv.style.display = 'block';
    
    try {
        const response = await fetch(`${API_BASE}/sync_all`);
        const data = await response.json();
        
        if (response.ok) {
            messageDiv.className = 'message success';
            messageDiv.textContent = `✅ ${data.message || '동기화 완료'}`;
            
            setTimeout(() => {
                refreshAll();
            }, 1000);
        } else {
            messageDiv.className = 'message error';
            messageDiv.textContent = `❌ 동기화 실패: ${data.message || '알 수 없는 오류'}`;
        }
    } catch (error) {
        messageDiv.className = 'message error';
        messageDiv.textContent = `❌ 네트워크 오류: ${error.message}`;
    }
}

// 블록 복구
async function recoverBlock() {
    const blockIndex = document.getElementById('recover-block-index').value;
    
    if (!blockIndex) {
        alert('블록 인덱스를 입력하세요.');
        return;
    }
    
    const messageDiv = document.getElementById('recover-message');
    messageDiv.className = 'message info';
    messageDiv.textContent = `🔧 블록 ${blockIndex} 복구 중...`;
    messageDiv.style.display = 'block';
    
    try {
        const response = await fetch(`${API_BASE}/recover_block/${blockIndex}`);
        const data = await response.json();
        
        if (response.ok) {
            messageDiv.className = 'message success';
            messageDiv.textContent = `✅ ${data.message || '블록 복구 완료'} (수집된 청크: ${data.collected_chunks || 0})`;
            
            setTimeout(() => {
                refreshAll();
            }, 1000);
        } else {
            messageDiv.className = 'message error';
            messageDiv.textContent = `❌ 복구 실패: ${data.message || '알 수 없는 오류'}`;
        }
    } catch (error) {
        messageDiv.className = 'message error';
        messageDiv.textContent = `❌ 네트워크 오류: ${error.message}`;
    }
}

// 자동 새로고침 토글
function autoRefresh() {
    const btn = document.getElementById('auto-refresh-btn');
    
    if (isAutoRefreshing) {
        clearInterval(autoRefreshInterval);
        isAutoRefreshing = false;
        btn.textContent = '▶️ 자동 새로고침 시작';
        btn.className = 'btn btn-secondary';
    } else {
        autoRefreshInterval = setInterval(refreshChain, 5000);
        isAutoRefreshing = true;
        btn.textContent = '⏸️ 자동 새로고침 중지';
        btn.className = 'btn btn-info';
    }
}

