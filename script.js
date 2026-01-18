// ==================== CONFIGURATION ====================
const API_BASE = window.location.origin;
const SECURITY_CONFIG = Object.freeze({
    TOKEN_KEY: 'auth_token',
    SESSION_KEY: 'session_data',
    MAX_TOKEN_AGE: 8 * 60 * 60 * 1000,
    RATE_LIMIT_WINDOW: 60000
});

// ==================== GLOBAL STATE ====================
let sessionData = {
    authenticated: false,
    token: null,
    clientData: null,
    businessType: null
};
let currentBusinessType = 'restaurant';
let orderRefreshInterval = null;
let notificationCheckInterval = null;

// ==================== SECURITY UTILITIES ====================
function sanitizeInput(input) {
    if (!input) return '';
    const element = document.createElement('div');
    element.textContent = String(input);
    return element.innerHTML;
}

function setTextContent(element, text) {
    if (element && element.nodeType === 1) {
        element.textContent = String(text);
    }
}

function secureStoreToken(token) {
    if (!token || typeof token !== 'string') return false;
    try {
        const tokenData = {
            value: token,
            timestamp: Date.now(),
            expiresAt: Date.now() + SECURITY_CONFIG.MAX_TOKEN_AGE
        };
        sessionStorage.setItem(SECURITY_CONFIG.TOKEN_KEY, JSON.stringify(tokenData));
        return true;
    } catch (e) {
                return false;
    }
}

function secureRetrieveToken() {
    try {
        const stored = sessionStorage.getItem(SECURITY_CONFIG.TOKEN_KEY);
        if (!stored) return null;
        
        const tokenData = JSON.parse(stored);
        if (Date.now() > tokenData.expiresAt) {
            sessionStorage.removeItem(SECURITY_CONFIG.TOKEN_KEY);
            return null;
        }
        return tokenData.value;
    } catch (e) {
                return null;
    }
}

function secureRemoveToken() {
    try {
        sessionStorage.removeItem(SECURITY_CONFIG.TOKEN_KEY);
        sessionStorage.removeItem(SECURITY_CONFIG.SESSION_KEY);
    } catch (e) {
            }
}

// ==================== SECURE FETCH WRAPPER ====================
async function secureFetch(url, options = {}) {
    const secureOptions = {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        }
    };
    
    const token = secureRetrieveToken();
    if (token) {
        secureOptions.headers['Authorization'] = `Bearer ${token}`;
    }
    
    if (options.body instanceof FormData) {
        delete secureOptions.headers['Content-Type'];
    }
    
    try {
        const response = await fetch(url, secureOptions);
        
        if (response.status === 401) {
            secureRemoveToken();
            sessionData.authenticated = false;
            showLogin();
            throw new Error('Session expired. Please login again.');
        }
        
        return response;
    } catch (error) {
                throw error;
    }
}

// ==================== ALERT SYSTEM ====================
function showAlert(elementId, message, type = 'error') {
    const alertDiv = document.getElementById(elementId);
    if (!alertDiv) return;
    
    alertDiv.className = `alert alert-${type}`;
    setTextContent(alertDiv, message);
    alertDiv.style.display = 'block';
    
    setTimeout(() => {
        alertDiv.style.display = 'none';
    }, 5000);
}

// ==================== NAVIGATION ====================
function showLogin() {
    document.getElementById('loginPage').classList.remove('hidden');
    document.getElementById('registerPage').classList.add('hidden');
    document.getElementById('dashboardPage').classList.add('hidden');
}

function showRegister() {
    document.getElementById('loginPage').classList.add('hidden');
    document.getElementById('registerPage').classList.remove('hidden');
    document.getElementById('dashboardPage').classList.add('hidden');
}

function showDashboard() {
    document.getElementById('loginPage').classList.add('hidden');
    document.getElementById('registerPage').classList.add('hidden');
    document.getElementById('dashboardPage').classList.remove('hidden');
    
    document.querySelectorAll('.restaurant-only').forEach(el => {
        el.style.display = 'flex';
    });
    
    showSection('dashboard');
    startAutoRefresh();
}

function showSection(sectionName) {
    const sections = ['dashboard', 'customers', 'support', 'documents', 'payment', 'orders', 'confirmedOrders'];
    sections.forEach(section => {
        const element = document.getElementById(`${section}Section`);
        if (element) element.classList.add('hidden');
    });
    
    const targetSection = document.getElementById(`${sectionName}Section`);
    if (targetSection) {
        targetSection.classList.remove('hidden');
    }
    
    if (sectionName === 'orders') {
        loadPendingOrders();
    } else if (sectionName === 'confirmedOrders') {
        loadConfirmedOrders();
    } else if (sectionName === 'payment') {
        loadPaymentLink();
    } else if (sectionName === 'dashboard') {
        loadDashboardStats();
    }
    
    closeSidebar();
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('overlay');
    sidebar.classList.toggle('active');
    overlay.classList.toggle('active');
}

function closeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('overlay');
    sidebar.classList.remove('active');
    overlay.classList.remove('active');
}

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', function() {
    const token = secureRetrieveToken();
    const storedSession = sessionStorage.getItem(SECURITY_CONFIG.SESSION_KEY);
    
    if (token && storedSession) {
        try {
            sessionData.token = token;
            sessionData.clientData = JSON.parse(storedSession);
            sessionData.authenticated = true;
            showDashboard();
        } catch (e) {
                        showLogin();
        }
    } else {
        showLogin();
    }
    
    attachFormHandlers();
    requestNotificationPermission();
});

function attachFormHandlers() {
    const loginForm = document.getElementById('loginForm');
    if (loginForm) loginForm.addEventListener('submit', handleLogin);
    
    const registerForm = document.getElementById('registerForm');
    if (registerForm) registerForm.addEventListener('submit', handleRegister);
    
    const addCustomerForm = document.getElementById('addCustomerForm');
    if (addCustomerForm) addCustomerForm.addEventListener('submit', handleAddCustomer);
    
    const addNonMemberForm = document.getElementById('addNonMemberForm');
    if (addNonMemberForm) addNonMemberForm.addEventListener('submit', handleAddNonMember);
    
    const uploadDocForm = document.getElementById('uploadDocumentForm');
    if (uploadDocForm) uploadDocForm.addEventListener('submit', handleUploadDocument);
    
    const paymentForm = document.getElementById('paymentLinkForm');
    if (paymentForm) paymentForm.addEventListener('submit', handleUpdatePaymentLink);
}

async function handleLogin(event) {
    event.preventDefault();
    
    const emailInput = document.getElementById('loginEmail');
    const passwordInput = document.getElementById('loginPassword');
    
    // Sanitize and normalize email
    const email = emailInput.value.trim().toLowerCase();
    const password = passwordInput.value; // Don't trim passwords!
    
    if (!email || !password) {
        showAlert('loginAlert', 'Please fill in all fields', 'error');
        return;
    }
    
    // Validate email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        showAlert('loginAlert', 'Please enter a valid email address', 'error');
        return;
    }
    
    const loginBtn = event.target.querySelector('button[type=submit]');
    loginBtn.disabled = true;
    setTextContent(loginBtn, 'Logging in...');
    
    try {
        const response = await fetch(`${API_BASE}/api/login`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password })
        });
        
        const data = await response.json();
        
        if (response.ok && data.token) {
        secureStoreToken(data.token);
        sessionData.authenticated = true;
        sessionData.token = data.token;
        sessionData.clientData = data.clientdata || data.client_data;
        sessionStorage.setItem(SECURITY_CONFIG.SESSION_KEY, JSON.stringify(sessionData.clientData));
        
        showAlert('loginAlert', 'Login successful!', 'success');
        setTimeout(showDashboard, 1000);
        } else {
        showAlert('loginAlert', data.detail || 'Login failed', 'error');
        }
    } catch (error) {
                showAlert('loginAlert', 'Network error. Please try again.', 'error');
    } finally {
        loginBtn.disabled = false;
        setTextContent(loginBtn, 'Login');
    }
}


// ==================== REGISTRATION - FIXED FIELD NAMES ====================
async function handleRegister(event) {
    event.preventDefault();
    
    const businessName = document.getElementById('businessName').value.trim();
    const businessType = document.getElementById('businessType').value.trim();
    const ownerName = document.getElementById('ownerName').value.trim();
    const phone = document.getElementById('phone').value.trim();
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const verifyToken = document.getElementById('verifyToken').value.trim();
    const waPhoneId = document.getElementById('waPhoneId').value.trim();
    const waVerifyToken = document.getElementById('waVerifyToken').value.trim();
    const fileInput = document.getElementById('fileInput');
    const privacyCheckbox = document.getElementById('privacyCheckbox');
    
    if (!businessName || !businessType || !ownerName || !phone || !email || !password) {
        showAlert('registerAlert', 'Please fill in all required fields', 'error');
        return;
    }
    
    if (!privacyCheckbox.checked) {
        showAlert('registerAlert', 'Please accept the Privacy Policy', 'error');
        return;
    }
    
    if (password.length < 8) {
        showAlert('registerAlert', 'Password must be at least 8 characters', 'error');
        return;
    }
    
    // ✅ FIXED: Match backend parameter names exactly
    const formData = new FormData();
    formData.append('business_name', businessName);  // Changed from businessname
    formData.append('business_type', businessType);  // Changed from businesstype
    formData.append('owner_name', ownerName);        // Changed from ownername
    formData.append('phone', phone);
    formData.append('email', email);
    formData.append('password', password);
    formData.append('verify_token', verifyToken);    // Changed from verifytoken
    formData.append('wa_phone_id', waPhoneId);       // Changed from waphoneid
    formData.append('wa_verify_token', waVerifyToken); // Changed from waverifytoken
    
    if (fileInput.files.length > 0) {
        formData.append('uploaded_file', fileInput.files[0]); // Changed from uploadedfile
    }
    
    const registerBtn = document.getElementById('registerBtn');
    registerBtn.disabled = true;
    setTextContent(registerBtn, 'Registering...');
    
    try {
        const response = await fetch(`${API_BASE}/api/register`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showAlert('registerAlert', 'Registration successful! Please login.', 'success');
            setTimeout(() => showLogin(), 2000);
        } else {
            showAlert('registerAlert', data.detail || 'Registration failed', 'error');
        }
    } catch (error) {
                showAlert('registerAlert', 'Network error. Please try again.', 'error');
    } finally {
        registerBtn.disabled = false;
        setTextContent(registerBtn, 'Complete Registration');
    }
}

// ==================== ORDERS - WITH ORDER TYPE DISPLAY ====================
async function loadPendingOrders() {
    const container = document.getElementById('pendingOrdersContainer');
    if (!container) return;
    
    container.innerHTML = '<p style="text-align: center; color: var(--secondary);">Loading orders...</p>';
    
    try {
        const response = await secureFetch(`${API_BASE}/api/orders`);
        const data = await response.json();
        
        if (response.ok) {
            currentBusinessType = data.business_type?.toLowerCase() || 'restaurant';
            
            if (data.orders && data.orders.length > 0) {
                renderUnifiedOrderCards(data.orders, container, false);
            } else {
                const icon = currentBusinessType === 'bakery' ? '🍰' : '🍽️';
                container.innerHTML = `<div class="empty-orders"><div class="empty-orders-icon">${icon}</div><p>No pending orders</p></div>`;
            }
        } else {
            container.innerHTML = '<p style="color: var(--error);">Error loading orders</p>';
        }
    } catch (error) {
        container.innerHTML = '<p style="color: var(--error);">Error loading orders</p>';
    }
}
async function loadConfirmedOrders() {
    const container = document.getElementById('confirmedOrdersContainer');
    if (!container) return;
    
    container.innerHTML = '<p style="text-align: center; color: var(--secondary);">Loading confirmed orders...</p>';
    
    try {
        const response = await secureFetch(`${API_BASE}/api/confirmed-orders`);
        const data = await response.json();
        
        if (response.ok) {
            currentBusinessType = data.business_type?.toLowerCase() || 'restaurant';
            
            if (data.orders && data.orders.length > 0) {
                renderUnifiedOrderCards(data.orders, container, true);
            } else {
                container.innerHTML = '<div class="empty-orders"><div class="empty-orders-icon">✅</div><p>No confirmed orders</p></div>';
            }
        } else {
            container.innerHTML = '<p style="color: var(--error);">Error loading orders</p>';
        }
    } catch (error) {
        container.innerHTML = '<p style="color: var(--error);">Error loading orders</p>';
    }
}

// ==================== UNIFIED ORDER CARD RENDERER ====================
function renderUnifiedOrderCards(orders, container, isConfirmed) {
    container.innerHTML = '';
    
    orders.forEach(order => {
        const orderCard = document.createElement('div');
        orderCard.className = 'universal-order-card';
        
        const orderId = order.order_id || 'UNKNOWN';
        const customerHash = order.customer_hash || '';
        const customerName = order.customer_name || 'Unknown Customer';
        const customerPhone = order.customer_phone || 'N/A';
        const customerAddress = order.customer_address || 'No address';
        const items = order.items || [];
        const total = parseFloat(order.total || 0);
        const orderType = order.Type || 'Not specified';
        
        const orderIdShort = orderId.substring(0, 8).toUpperCase();
        
        // Build items HTML
        let itemsHTML = '';
        let hasCustomCake = false;
        
        items.forEach(item => {
            if (item.type === 'custom_cake') {
                hasCustomCake = true;
                const weight = item.weight || 'N/A';
                const flavour = item.flavour || 'N/A';
                const cakeMessage = item.cake_message || '';
                const delivery = item.delivery_datetime || 'ASAP';
                const price = parseFloat(item.price || 0);
                
                itemsHTML += `
                    <div class="custom-cake-section">
                        <div class="custom-cake-header">
                            <span class="cake-icon">🎂</span>
                            <span class="cake-title">Custom Cake</span>
                        </div>
                        <div class="cake-specs">
                            <div class="cake-spec">
                                <span class="spec-label">Weight</span>
                                <span class="spec-value">${sanitizeInput(weight)}</span>
                            </div>
                            <div class="cake-spec">
                                <span class="spec-label">Flavour</span>
                                <span class="spec-value">${sanitizeInput(flavour)}</span>
                            </div>
                            <div class="cake-spec">
                                <span class="spec-label">Delivery</span>
                                <span class="spec-value">${sanitizeInput(delivery)}</span>
                            </div>
                            <div class="cake-spec">
                                <span class="spec-label">Price</span>
                                <span class="spec-value">₹${price.toFixed(2)}</span>
                            </div>
                        </div>
                        ${cakeMessage ? `
                        <div class="cake-message">
                            <span class="message-icon">💬</span>
                            <div class="message-content">
                                <div class="message-label">Message on Cake</div>
                                <div class="message-text">"${sanitizeInput(cakeMessage)}"</div>
                            </div>
                        </div>
                        ` : ''}
                    </div>
                `;
            } else {
                const foodName = item.food_name || 'Unknown Item';
                const quantity = parseInt(item.quantity || 1);
                const price = parseFloat(item.price || 0);
                
                itemsHTML += `
                    <div class="order-item">
                        <div class="item-info">
                            <span class="item-name">${sanitizeInput(foodName)}</span>
                        </div>
                        <div class="item-details">
                            <span class="item-qty">×${quantity}</span>
                            <span class="item-price">₹${(price * quantity).toFixed(2)}</span>
                        </div>
                    </div>
                `;
            }
        });
        
        const badgeClass = isConfirmed ? 'confirmed' : 'pending';
        const badgeText = isConfirmed ? '✅ CONFIRMED' : '🆕 NEW';
        
        orderCard.innerHTML = `
            <div class="order-card-header">
                <div class="order-id-section">
                    <span class="order-id-label">Order ID</span>
                    <span class="order-id-value">#${sanitizeInput(orderIdShort)}</span>
                </div>
                <span class="order-badge ${badgeClass}">${badgeText}</span>
            </div>
            
            <div class="customer-section">
                <div class="customer-name">
                    <span class="customer-icon">👤</span>
                    ${sanitizeInput(customerName)}
                </div>
                <div class="customer-contact">
                    <div class="contact-row">
                        <span class="contact-icon">📞</span>
                        <span class="order-type-text">${sanitizeInput(customerPhone)}</span>
                    </div>
                    <div class="contact-row">
                        <span class="contact-icon">📍</span>
                        <span class="order-type-text">${sanitizeInput(customerAddress)}</span>
                    </div>
                    <div class="contact-row">
                        <span class="contact-icon">📦</span>
                        <span class="order-type-text">Type:</span>
                        <span class="delivery-badge">${sanitizeInput(orderType)}</span>
                    </div>
                </div>
            </div>
            
            ${hasCustomCake ? '' : '<div class="items-section"><div class="items-header">📋 Order Items</div>'}
            ${itemsHTML}
            ${hasCustomCake ? '' : '</div>'}
            
            <div class="order-total-section">
                <span class="total-label">Total Amount</span>
                <span class="total-value">₹${total.toFixed(2)}</span>
            </div>
            
            ${!isConfirmed ? `
                <div class="order-actions">
                    <button class="btn-call" onclick="window.open('tel:${customerPhone}', '_self')">📞</button>
                    <button class="btn-confirm" onclick="confirmOrder('${orderId}', '${customerHash}')">
                        ✅ Confirm Order
                    </button>
                </div>
            ` : `
                <div class="order-actions">
                    <button class="btn-call" onclick="window.open('tel:${customerPhone}', '_self')" style="width: 100%;">
                        📞 Call Customer
                    </button>
                </div>
            `}
        `;
        
        container.appendChild(orderCard);
    });
}

// ==================== INITIALIZE & LOAD DATA ====================
async function loadClientData() {
    try {
        const response = await fetch('/api/verify-session', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) {
            throw new Error('Session invalid');
        }
        
        const data = await response.json();
        const clientData = data.clientdata;
        
        // **KEY ADDITION: Get business type from client data**
        businessType = (clientData['Business Type'] || clientData['businesstype'] || 'restaurant').toLowerCase();
                
        // Store other client info
        document.getElementById('businessName').textContent = clientData['Business Name'] || 'Business';
        // ... rest of existing client data handling
        
    } catch (error) {
                showNotification('Failed to load business information', 'error');
    }
}

// ==================== ORDER RENDERING FUNCTIONS ====================

// **ORIGINAL RESTAURANT RENDER FUNCTION** (Keep as-is)
function renderOrderCards(orders, container, isConfirmed) {
    if (!orders || orders.length === 0) {
        const icon = isConfirmed ? '✓' : '⏰';
        const message = isConfirmed ? 'No confirmed orders yet' : 'No pending orders';
        container.innerHTML = `<div class="empty-orders"><div class="empty-orders-icon">${icon}</div><p>${message}</p></div>`;
        return;
    }

    container.innerHTML = '';

    orders.forEach(order => {
        const orderCard = document.createElement('div');
        orderCard.className = 'order-card';

        const orderId = order.orderid || 'UNKNOWN';
        const customerHash = order.customerhash;
        const customerName = order.customername || 'Unknown Customer';
        const customerPhone = order.customerphone || 'Not provided';
        const customerAddress = order.customeraddress || 'No address provided';
        const items = order.items || [];
        const total = parseFloat(order.total) || 0;
        const orderType = order.ordertype || order.Type || 'Not specified';

        let itemsHTML = '';
        let calculatedTotal = 0;

        if (Array.isArray(items) && items.length > 0) {
            items.forEach(item => {
                const foodName = item.foodname || 'Unknown Item';
                const size = item.size || null;
                const quantity = parseInt(item.quantity) || 1;
                const price = parseFloat(item.price) || 0;
                calculatedTotal += (price * quantity);

                const sizeDisplay = (size && size !== 'regular') ? 
                    `<span style="color: #64748b; font-size: 0.9em;"> (${sanitizeInput(size)})</span>` : '';

                itemsHTML += `
                    <div class="order-item">
                        <span class="item-name">${sanitizeInput(foodName)}${sizeDisplay}</span>
                        <span class="item-quantity">×${quantity}</span>
                        <span class="item-price">₹${(price * quantity).toFixed(2)}</span>
                    </div>
                `;
            });
        }

        const finalTotal = calculatedTotal > 0 ? calculatedTotal : total;
        const orderIdShort = orderId.substring(0, 8).toUpperCase();

        orderCard.innerHTML = `
            <div class="order-header">
                <span class="order-id">Order #${sanitizeInput(orderIdShort)}</span>
                <span class="order-type-badge">${sanitizeInput(orderType)}</span>
            </div>
            <div class="customer-info">
                <div class="customer-name">👤 ${sanitizeInput(customerName)}</div>
                <div class="customer-phone">📱 ${sanitizeInput(customerPhone)}</div>
                ${orderType.toLowerCase() === 'delivery' ? 
                    `<div class="customer-address">📍 ${sanitizeInput(customerAddress)}</div>` : ''}
            </div>
            <div class="order-items">${itemsHTML}</div>
            <div class="order-total">Total: ₹${finalTotal.toFixed(2)}</div>
            ${!isConfirmed ? `
                <div class="order-actions">
                    <button class="btn-secondary" onclick="window.open('tel:${customerPhone}', '_self')">📞 Call</button>
                    <button class="btn-primary" onclick="confirmOrder('${orderId}', '${customerHash}')">✓ Confirm</button>
                </div>
            ` : ''}
        `;

        container.appendChild(orderCard);
    });
}

async function confirmOrder(orderId, customerHash) {
    if (!orderId || !customerHash) {
        showAlert('dashboardAlert', 'Invalid order data', 'error');
        return;
    }
    
    if (!confirm('Confirm this order? Customer will be notified via WhatsApp.')) {
        return;
    }
    
    try {
        // FIXED: Send customer_hash in request body instead of query parameter
        const response = await secureFetch(`${API_BASE}/api/confirm-order/${orderId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                customer_hash: customerHash
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showAlert('dashboardAlert', `✅ Order confirmed! WhatsApp sent to ${data.customer_name}`, 'success');
            
            // Refresh both order lists
            await loadPendingOrders();
            await loadConfirmedOrders();
        } else {
            showAlert('dashboardAlert', data.detail || 'Failed to confirm order', 'error');
        }
    } catch (error) {
                showAlert('dashboardAlert', 'Failed to confirm order. Please try again.', 'error');
    }
}

// Make sure these functions are globally accessible
window.loadPendingOrders = loadPendingOrders;
window.loadConfirmedOrders = loadConfirmedOrders;
window.confirmOrder = confirmOrder;

// ==================== AUTO REFRESH ====================
function startAutoRefresh() {
    if (orderRefreshInterval) clearInterval(orderRefreshInterval);
    if (notificationCheckInterval) clearInterval(notificationCheckInterval);
    
    orderRefreshInterval = setInterval(() => {
        if (sessionData.authenticated) {
            const ordersSection = document.getElementById('ordersSection');
            const confirmedSection = document.getElementById('confirmedOrdersSection');
            
            if (ordersSection && !ordersSection.classList.contains('hidden')) {
                loadPendingOrders();
            }
            if (confirmedSection && !confirmedSection.classList.contains('hidden')) {
                loadConfirmedOrders();
            }
        }
    }, 90000);
    
    notificationCheckInterval = setInterval(() => {
        if (sessionData.authenticated) {
            checkNewOrders();
        }
    }, 60000);
}

async function checkNewOrders() {
    try {
        const response = await secureFetch(`${API_BASE}/api/new-orders`);
        const data = await response.json();
        
        if (response.ok && data.has_new_order) {
            if (Notification.permission === 'granted') {
                new Notification('🔔 New Order Received!', {
                    body: 'You have a new pending order',
                    icon: '/static/icon.png'
                });
            }
            
            const ordersSection = document.getElementById('ordersSection');
            if (ordersSection && !ordersSection.classList.contains('hidden')) {
                loadPendingOrders();
            }
        }
    } catch (error) {
            }
}

function requestNotificationPermission() {
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }
}

// ==================== ADD CUSTOMER - FIXED FIELD NAMES ====================
async function handleAddCustomer(event) {
    event.preventDefault();
    
    const name = document.getElementById('customerName').value.trim();
    const phone = document.getElementById('customerPhone').value.trim();
    const planEndDate = document.getElementById('customerPlanEnd').value;
    
    if (!name || !phone || !planEndDate) {
        showAlert('dashboardAlert', 'Please fill in all customer fields', 'error');
        return;
    }
    
    const submitBtn = event.target.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    setTextContent(submitBtn, 'Adding...');
    
    try {
        // ✅ FIXED: Match backend parameter names
        const response = await secureFetch(`${API_BASE}/api/add-customer`, {
            method: 'POST',
            body: JSON.stringify({ 
                name: name, 
                phone: phone, 
                plan_end_date: planEndDate  // Changed from planenddate
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showAlert('dashboardAlert', 'Customer added successfully', 'success');
            event.target.reset();
        } else {
            showAlert('dashboardAlert', data.detail || 'Failed to add customer', 'error');
        }
    } catch (error) {
                showAlert('dashboardAlert', 'Failed to add customer', 'error');
    } finally {
        submitBtn.disabled = false;
        setTextContent(submitBtn, 'Add Customer');
    }
}

// ==================== ADD NON-MEMBER ====================
async function handleAddNonMember(event) {
    event.preventDefault();
    
    const name = document.getElementById('nonMemberName').value.trim();
    const phone = document.getElementById('nonMemberPhone').value.trim();
    
    if (!name || !phone) {
        showAlert('dashboardAlert', 'Please fill in all non-member fields', 'error');
        return;
    }
    
    const submitBtn = event.target.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    setTextContent(submitBtn, 'Adding...');
    
    try {
        const response = await secureFetch(`${API_BASE}/api/add-non-member`, {
            method: 'POST',
            body: JSON.stringify({ name, phone })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showAlert('dashboardAlert', 'Non-member added successfully', 'success');
            event.target.reset();
        } else {
            showAlert('dashboardAlert', data.detail || 'Failed to add non-member', 'error');
        }
    } catch (error) {
                showAlert('dashboardAlert', 'Failed to add non-member', 'error');
    } finally {
        submitBtn.disabled = false;
        setTextContent(submitBtn, 'Add Non-Member');
    }
}

// ==================== UPLOAD DOCUMENT ====================
async function handleUploadDocument(event) {
    event.preventDefault();
    
    const documentName = document.getElementById('documentName').value.trim();
    const fileInput = document.getElementById('newDocInput');
    
    if (!fileInput.files.length) {
        showAlert('dashboardAlert', 'Please select a document to upload', 'error');
        return;
    }
    
    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('document_file', file);
    formData.append('document_name', documentName);
    
    const submitBtn = event.target.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    setTextContent(submitBtn, 'Uploading...');
    
    try {
        const response = await secureFetch(`${API_BASE}/api/upload-document`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showAlert('dashboardAlert', 'Document uploaded successfully', 'success');
            event.target.reset();
            document.getElementById('newDocLabel').textContent = 'Click to upload document (PDF, TXT - Max 1MB)';
        } else {
            showAlert('dashboardAlert', data.detail || 'Upload failed', 'error');
        }
    } catch (error) {
                showAlert('dashboardAlert', 'Upload failed', 'error');
    } finally {
        submitBtn.disabled = false;
        setTextContent(submitBtn, 'Upload Document');
    }
}

function handleNewDocSelect(event) {
    const file = event.target.files[0];
    const label = document.getElementById('newDocLabel');
    
    if (file) {
        if (file.size > 1 * 1024 * 1024) {
            setTextContent(label, 'File too large (max 1MB)');
            event.target.value = '';
            return;
        }
        setTextContent(label, `Selected: ${file.name}`);
    } else {
        setTextContent(label, 'Click to upload document (PDF, TXT - Max 1MB)');
    }
}

// ==================== PAYMENT LINK ====================
async function loadPaymentLink() {
    const displayLink = document.getElementById('displayPaymentLink');
    const displayDesc = document.getElementById('displayPaymentDesc');
    
    if (sessionData.clientData && sessionData.clientData.payment_link) {
        setTextContent(displayLink, sessionData.clientData.payment_link);
        setTextContent(displayDesc, sessionData.clientData.payment_description || '');
    } else {
        setTextContent(displayLink, 'Not set yet');
        setTextContent(displayDesc, '');
    }
}

async function handleUpdatePaymentLink(event) {
    event.preventDefault();
    
    const paymentLink = document.getElementById('paymentLinkUrl').value.trim();
    const description = document.getElementById('paymentLinkDesc').value.trim();
    
    if (!paymentLink) {
        showAlert('dashboardAlert', 'Please enter a payment link', 'error');
        return;
    }
    
    try {
        new URL(paymentLink);
    } catch (e) {
        showAlert('dashboardAlert', 'Please enter a valid URL', 'error');
        return;
    }
    
    const submitBtn = event.target.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    setTextContent(submitBtn, 'Saving...');
    
    try {
        const response = await secureFetch(`${API_BASE}/api/update-payment-link`, {
            method: 'POST',
            body: JSON.stringify({ payment_link: paymentLink, description })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showAlert('dashboardAlert', 'Payment link updated successfully', 'success');
            setTextContent(document.getElementById('displayPaymentLink'), paymentLink);
            setTextContent(document.getElementById('displayPaymentDesc'), description);
        } else {
            showAlert('dashboardAlert', data.detail || 'Failed to update payment link', 'error');
        }
    } catch (error) {
                showAlert('dashboardAlert', 'Failed to update payment link', 'error');
    } finally {
        submitBtn.disabled = false;
        setTextContent(submitBtn, 'Save Payment Link');
    }
}

// ==================== DASHBOARD STATS ====================
async function loadDashboardStats() {
    try {
        const response = await secureFetch(`${API_BASE}/api/dashboard-stats`);
        const data = await response.json();
        
        if (response.ok) {
                    }
    } catch (error) {
            }
}

// ==================== SUPPORT ====================
function submitSupport() {
    const subject = document.getElementById('supportSubject').value.trim();
    const message = document.getElementById('supportMessage').value.trim();
    
    if (!subject || !message) {
        showAlert('dashboardAlert', 'Please fill in both subject and message', 'error');
        return;
    }
    
    const mailtoLink = `mailto:support@businessportal.com?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(message)}`;
    window.location.href = mailtoLink;
    showAlert('dashboardAlert', 'Opening your email client...', 'success');
}

// ==================== FILE UPLOAD HANDLERS ====================
function handleFileSelect(event) {
    const file = event.target.files[0];
    const label = document.getElementById('fileLabel');
    
    if (file) {
        if (file.size > 10 * 1024 * 1024) {
            setTextContent(label, 'File too large (max 10MB)');
            event.target.value = '';
            return;
        }
        setTextContent(label, `Selected: ${file.name}`);
    } else {
        setTextContent(label, 'Click to upload document (PDF, TXT - Max 10MB)');
    }
}
function displayOrders() {
        const pendingContainer = document.getElementById('pendingOrdersContainer');
        const confirmedContainer = document.getElementById('confirmedOrdersContainer');
        
        // **Conditional rendering based on business type**
        if (businessType === 'bakery') {
            renderBakeryOrderCards(pendingOrders, pendingContainer, false);
            renderBakeryOrderCards(confirmedOrders, confirmedContainer, true);
        } else {
            // Default to restaurant rendering
            renderOrderCards(pendingOrders, pendingContainer, false);
            renderOrderCards(confirmedOrders, confirmedContainer, true);
        }

        updateCounts();
    }
// ==================== PRIVACY MODAL ====================
function showPrivacyPolicy(event) {
    event.preventDefault();
    const modal = document.getElementById('privacyModal');
    if (modal) modal.classList.add('active');
}

function closePrivacyModal() {
    const modal = document.getElementById('privacyModal');
    if (modal) modal.classList.remove('active');
}

window.addEventListener('click', function(event) {
    const modal = document.getElementById('privacyModal');
    if (event.target === modal) {
        closePrivacyModal();
    }
});

// ==================== LOGOUT ====================
function logout() {
    if (orderRefreshInterval) clearInterval(orderRefreshInterval);
    if (notificationCheckInterval) clearInterval(notificationCheckInterval);
    
    secureRemoveToken();
    sessionData = {
        authenticated: false,
        token: null,
        clientData: null,
        businessType: null
    };
    showLogin();
}

// ==================== SESSION PERSISTENCE ====================
window.addEventListener('beforeunload', function() {
    if (sessionData.authenticated && sessionData.clientData) {
        try {
            sessionStorage.setItem(SECURITY_CONFIG.SESSION_KEY, JSON.stringify(sessionData.clientData));
        } catch (e) {
                    }
    }
});

// ==================== TOKEN EXPIRATION CHECK ====================
setInterval(() => {
    if (sessionData.authenticated) {
        const token = secureRetrieveToken();
        if (!token) {
            alert('Your session has expired. Please login again.');
            logout();
        }
    }
}, 60000);

// ==================== EXPOSE GLOBAL FUNCTIONS ====================
window.showLogin = showLogin;
window.showRegister = showRegister;
window.showSection = showSection;
window.toggleSidebar = toggleSidebar;
window.closeSidebar = closeSidebar;
window.logout = logout;
window.handleFileSelect = handleFileSelect;
window.handleNewDocSelect = handleNewDocSelect;
window.submitSupport = submitSupport;
window.showPrivacyPolicy = showPrivacyPolicy;
window.closePrivacyModal = closePrivacyModal;
window.confirmOrder = confirmOrder;

// ==================== FETCH BAKERY ORDERS ====================
async function fetchBakeryOrders() {
    try {
        const token = sessionStorage.getItem('auth_token') || localStorage.getItem('auth_token');

        if (!token) {
            const container = document.getElementById(containerSelector || 'pendingOrdersContainer');
            if (container) {
                container.innerHTML = '<p style="text-align: center; color: var(--text-secondary); padding: 40px;">Please login to view orders</p>';
            }
            return;
        }

        const response = await fetch(`${API_BASE}/bakery/orders`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.orders && Array.isArray(data.orders)) {
            renderBakeryOrderCards(data.orders, 'pendingOrdersContainer');
        } else {
            renderBakeryOrderCards([]);
        }
    } catch (error) {
        const container = document.getElementById(containerSelector || 'pendingOrdersContainer');
        if (container) {
            container.innerHTML = '<p style="text-align: center; color: var(--danger); padding: 40px;">Error loading orders. Please refresh the page.</p>';
        }
    }
}