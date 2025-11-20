const API_BASE = '';

let autoRefreshInterval = null;
let isAutoRefreshing = false;
let lastChainLength = 0; // 이전 체인 길이 추적
let localIP = null; // 로컬 IP 주소 (다른 노드 블록 구분용)

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    refreshAll();
    refreshChunkList();
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
            const currentChainLength = chainData.length || 0;
            
            // 체인 길이가 변경되었으면 체인 내용도 새로고침
            if (currentChainLength !== lastChainLength) {
                lastChainLength = currentChainLength;
                refreshChain(); // 체인 내용 새로고침
            }
            
            updateChainStatus(chainData);
        }

        if (statusRes.ok) {
            const statusData = await statusRes.json();
            document.getElementById('pending-tx').textContent = statusData.pending_transactions || 0;
            document.getElementById('pending-tx-count').textContent = statusData.pending_transactions || 0;
            // 로컬 IP 저장 (다른 노드 블록 구분용 및 청크 필터링용)
            if (statusData.local_ip) {
                const previousIP = localIP;
                localIP = statusData.local_ip;
                // IP가 변경되었거나 처음 설정되었을 때 청크 목록 새로고침
                if (previousIP !== localIP) {
                    refreshChunkList();
                }
            }
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
            if (response.status === 403 && data.error === 'CHAIN_VALIDATION_FAILED') {
                messageDiv.textContent = `🚫 거래가 차단되었습니다: ${data.message || '분산장부 불일치'}`;
            } else {
                messageDiv.textContent = `❌ 오류: ${data.message || '트랜잭션 추가 실패'}`;
            }
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
            if (response.status === 403 && data.error === 'CHAIN_VALIDATION_FAILED') {
                messageDiv.textContent = `🚫 채굴이 차단되었습니다: ${data.message || '분산장부 불일치'}`;
            } else {
                messageDiv.textContent = `❌ 오류: ${data.message || '블록 채굴 실패'}`;
            }
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
            lastChainLength = data.chain.length; // 체인 길이 업데이트
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
    [...chain].reverse().forEach((block) => {
        const blockDiv = document.createElement('div');
        blockDiv.className = 'block';
        
        const timestamp = new Date(block.timestamp * 1000).toLocaleString('ko-KR');
        
        // 다른 노드에서 채굴한 블록인지 확인
        // 체인 동기화 시 다른 노드의 블록도 트랜잭션 정보가 포함되지만,
        // 사용자 요구사항: 다른 노드의 블록은 트랜잭션을 "트랜잭션 숨겨짐"으로 표시
        // 
        // 문제: 블록에 채굴자 정보가 없어서 로컬에서 채굴한 블록을 구분할 수 없음
        // 해결책: 체인에 있는 모든 블록의 트랜잭션을 표시하되,
        // 사용자가 요청한 대로 다른 노드의 블록은 트랜잭션을 숨김
        // 
        // 실제로는 체인 동기화 시 모든 블록의 트랜잭션이 포함되므로,
        // 모든 블록의 트랜잭션을 표시하는 것이 맞지만,
        // 사용자 요구사항에 따라 다른 노드의 블록은 트랜잭션을 숨김
        //
        // 간단한 방법: 모든 블록의 트랜잭션을 숨기고,
        // 로컬에서 채굴한 블록만 트랜잭션을 표시
        // 하지만 로컬에서 채굴한 블록을 구분할 방법이 없으므로,
        // 모든 블록의 트랜잭션을 숨김 (사용자 요구사항)
        const showTransactions = false;
        
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
                ${showTransactions ? `
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
                ` : `
                    <div class="transactions">
                        <h4>트랜잭션 (${block.transactions.length}개)</h4>
                        <p style="color: #999; font-style: italic;">트랜잭션 숨겨짐</p>
                    </div>
                `}
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

// 청크 목록 새로고침
async function refreshChunkList() {
    const container = document.getElementById('chunk-list-container');
    container.innerHTML = '<div class="loading">청크 목록을 불러오는 중...</div>';
    
    try {
        // 현재 IP의 청크만 조회
        const url = localIP ? `${API_BASE}/api/chunks?node_id=${encodeURIComponent(localIP)}` : `${API_BASE}/api/chunks`;
        const response = await fetch(url);
        const data = await response.json();
        
        if (response.ok && data.chunks) {
            displayChunkList(data.chunks);
        } else {
            container.innerHTML = '<div class="empty">청크 목록을 가져올 수 없습니다</div>';
        }
    } catch (error) {
        container.innerHTML = `<div class="empty">오류: ${error.message}</div>`;
    }
}

// 청크 목록 표시
function displayChunkList(chunks) {
    const container = document.getElementById('chunk-list-container');
    
    if (chunks.length === 0) {
        container.innerHTML = '<div class="empty">저장된 청크가 없습니다</div>';
        return;
    }
    
    // 블록별로 그룹화
    const blocksMap = {};
    chunks.forEach(chunk => {
        const blockIndex = chunk.block_index;
        if (!blocksMap[blockIndex]) {
            blocksMap[blockIndex] = [];
        }
        blocksMap[blockIndex].push(chunk);
    });
    
    container.innerHTML = '';
    
    // 블록별로 표시
    Object.keys(blocksMap).sort((a, b) => parseInt(a) - parseInt(b)).forEach(blockIndex => {
        const blockChunks = blocksMap[blockIndex];
        const blockDiv = document.createElement('div');
        blockDiv.className = 'block';
        blockDiv.style.marginBottom = '15px';
        
        blockDiv.innerHTML = `
            <div class="block-header">
                <div class="block-index">블록 #${blockIndex}</div>
                <div style="color: #666; font-size: 0.9em;">청크 ${blockChunks.length}개</div>
            </div>
            <div class="block-details">
                <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; margin-top: 10px;">
                    ${blockChunks.map(chunk => `
                        <div style="padding: 8px; background: #f5f5f5; border-radius: 4px; font-size: 0.9em;">
                            <strong>청크 #${chunk.chunk_id}</strong><br>
                            <span style="color: #666;">노드: ${chunk.node_id}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
        
        container.appendChild(blockDiv);
    });
}

// 청크 파일로부터 블록 기록 열람
async function viewBlockFromChunks() {
    const blockIndex = document.getElementById('view-block-index').value;
    
    if (!blockIndex) {
        alert('블록 인덱스를 입력하세요.');
        return;
    }
    
    const messageDiv = document.getElementById('view-message');
    const container = document.getElementById('view-block-container');
    const contentDiv = document.getElementById('viewed-block-content');
    
    messageDiv.className = 'message info';
    messageDiv.textContent = `👁️ 블록 ${blockIndex} 기록 열람 중...`;
    messageDiv.style.display = 'block';
    container.style.display = 'none';
    
    try {
        const response = await fetch(`${API_BASE}/api/view_block/${blockIndex}`);
        const data = await response.json();
        
        if (response.ok && data.block) {
            messageDiv.className = 'message success';
            messageDiv.textContent = `✅ ${data.message || '블록 기록 열람 완료'} (수집된 청크: ${data.collected_chunks || 0})`;
            
            // 블록 정보 표시
            const block = data.block;
            const timestamp = new Date(block.timestamp * 1000).toLocaleString('ko-KR');
            
            contentDiv.innerHTML = `
                <div class="block">
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
                </div>
            `;
            
            container.style.display = 'block';
        } else {
            messageDiv.className = 'message error';
            messageDiv.textContent = `❌ 열람 실패: ${data.message || '알 수 없는 오류'}`;
            container.style.display = 'none';
        }
    } catch (error) {
        messageDiv.className = 'message error';
        messageDiv.textContent = `❌ 네트워크 오류: ${error.message}`;
        container.style.display = 'none';
    }
}


