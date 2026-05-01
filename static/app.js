document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('messageForm');
    const emptyState = document.getElementById('emptyState');
    const loadingState = document.getElementById('loadingState');
    const resultsState = document.getElementById('resultsState');

    // ── Real-Time Context Engine ──────────────────────────────────────
    async function fetchContext() {
        try {
            const res = await fetch('/api/context');
            const ctx = await res.json();

            // Auto-select the best trigger in the dropdown
            const triggerSelect = document.getElementById('trigger');
            if (ctx.suggested_trigger && triggerSelect) {
                triggerSelect.value = ctx.suggested_trigger;
            }

            // Build the context banner
            const banner = document.getElementById('contextBanner');
            if (!banner) return;

            const parts = [];
            parts.push(`🕐 ${ctx.current_time}`);
            parts.push(ctx.day_type === 'weekend' ? '📅 Weekend' : `📅 ${ctx.day_type.charAt(0).toUpperCase() + ctx.day_type.slice(1)}`);
            const timeLabel = ctx.time_of_day.replace(/\b\w/g, c => c.toUpperCase());
            parts.push(`⏰ ${timeLabel}`);
            if (ctx.festival) parts.push(`🎉 ${ctx.festival}`);

            banner.innerHTML = `
                <div class="flex items-center flex-wrap gap-3">
                    <span class="text-xs font-semibold text-purple-300 uppercase tracking-wider">⚡ Live Context</span>
                    ${parts.map(p => `<span class="bg-slate-800 text-slate-200 text-xs px-3 py-1 rounded-full border border-slate-600">${p}</span>`).join('')}
                    ${ctx.festival ? '' : `<span class="ml-auto text-xs text-slate-400">Trigger auto-set to <span class="text-purple-300 font-medium">${ctx.suggested_trigger}</span></span>`}
                </div>
                ${ctx.festival ? `<p class="text-xs text-yellow-300 mt-2">🎊 Festival detected: <strong>${ctx.festival}</strong> — Festival trigger auto-selected!</p>` : ''}
            `;
            banner.classList.remove('hidden');
        } catch (e) {
            // Context fetch failed silently
        }
    }

    fetchContext();
    // Refresh context every 60 seconds
    setInterval(fetchContext, 60000);
    // ─────────────────────────────────────────────────────────────────


    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Hide states
        emptyState.classList.add('hidden');
        resultsState.classList.add('hidden');
        resultsState.classList.remove('fade-in');
        loadingState.classList.remove('hidden');

        // Get data
        const payload = {
            category: document.getElementById('category').value,
            merchant_name: document.getElementById('merchant_name').value,
            offer: document.getElementById('offer').value,
            trigger: document.getElementById('trigger').value,
            customer_context: document.getElementById('customer_context').value,
            tone_style: document.getElementById('tone_style').value
        };

        try {
            const response = await fetch('/api/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error('API request failed');
            }

            const data = await response.json();
            
            const resultsContainer = document.getElementById('resultsState');
            resultsContainer.innerHTML = `
                <!-- Merchant Insights Dashboard -->
                <div class="glass-panel rounded-2xl p-6 md:p-8 mb-6 border-l-4 border-l-purple-500 relative overflow-hidden">
                    <div class="absolute top-0 right-0 w-32 h-32 bg-purple-500/10 rounded-full blur-2xl transform translate-x-10 -translate-y-10"></div>
                    
                    <h3 class="text-xl font-bold text-slate-100 mb-4 flex items-center">
                        <i class="fas fa-chart-pie text-purple-400 mr-3"></i> Merchant Insights Dashboard
                    </h3>
                    
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div class="bg-slate-900/40 rounded-xl p-4 border border-slate-700/50">
                            <h4 class="text-xs text-slate-400 uppercase tracking-wider font-semibold mb-2"><i class="fas fa-search-dollar mr-2 text-blue-400"></i>Analysis</h4>
                            <p class="text-slate-200 text-sm leading-relaxed">${data.merchant_insights.analysis}</p>
                        </div>
                        <div class="bg-slate-900/40 rounded-xl p-4 border border-slate-700/50">
                            <h4 class="text-xs text-slate-400 uppercase tracking-wider font-semibold mb-2"><i class="fas fa-lightbulb mr-2 text-yellow-400"></i>Strategy</h4>
                            <p class="text-slate-200 text-sm leading-relaxed">${data.merchant_insights.strategy}</p>
                        </div>
                        <div class="bg-slate-900/40 rounded-xl p-4 border border-slate-700/50 flex flex-col justify-center items-center text-center">
                            <h4 class="text-xs text-slate-400 uppercase tracking-wider font-semibold mb-2"><i class="fas fa-tags mr-2 text-pink-400"></i>Suggested Discount</h4>
                            <span class="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-pink-500">${data.merchant_insights.suggested_discount}</span>
                        </div>
                    </div>

                    ${data.learning_insight ? `
                    <div class="mt-4 flex items-start bg-slate-900/50 rounded-xl p-4 border border-purple-500/30">
                        <span class="text-2xl mr-3">🧠</span>
                        <div>
                            <h4 class="text-xs font-semibold text-purple-300 uppercase tracking-wider mb-1">Learning Engine</h4>
                            <p class="text-slate-300 text-sm">${data.learning_insight.insight_text}</p>
                        </div>
                    </div>` : ''}
                </div>

                <!-- A/B Testing Recommendation -->
                <div class="glass-panel rounded-2xl p-6 mb-6 border-l-4 border-l-green-400 relative overflow-hidden bg-gradient-to-r from-slate-900/80 to-slate-800/80">
                    <div class="flex items-start">
                        <div class="bg-green-400/20 p-3 rounded-full mr-4 shrink-0">
                            <i class="fas fa-trophy text-xl text-green-400"></i>
                        </div>
                        <div>
                            <h3 class="text-lg font-bold text-slate-200 mb-1">A/B Test Recommendation</h3>
                            <p class="text-slate-300 text-sm leading-relaxed">${data.ab_test_recommendation}</p>
                        </div>
                    </div>
                </div>

                <div class="mb-4 pb-2 border-b border-slate-700/50">
                    <h3 class="text-2xl font-bold text-slate-200">
                        <i class="fas fa-layer-group mr-2 text-purple-400"></i> Strategy Modes
                    </h3>
                    <p class="text-slate-400 text-sm mt-1">Select the strategy that best fits your current marketing goal.</p>
                </div>
                <div class="grid grid-cols-1 gap-6" id="modesGrid"></div>
            `;
            
            const grid = document.getElementById('modesGrid');
            
            data.modes.forEach((mode) => {
                let scoreColor = 'text-green-400';
                if (mode.confidence_score < 70) scoreColor = 'text-orange-400';
                else if (mode.confidence_score < 90) scoreColor = 'text-yellow-400';

                const tagsHTML = mode.tags.map(tag => 
                    `<span class="text-xs tag-badge px-3 py-1 rounded-full capitalize font-medium tracking-wide">${tag}</span>`
                ).join('');

                const cardHTML = `
                    <div class="glass-panel rounded-2xl p-6 relative overflow-hidden border-slate-600 hover:border-purple-500/50 transition-all group">
                        <div class="absolute top-0 left-0 w-1 h-full bg-slate-600 group-hover:bg-gradient-to-b group-hover:from-purple-500 group-hover:to-pink-500 transition-all"></div>
                        
                        <div class="flex justify-between items-start mb-4">
                            <span class="bg-slate-800 text-white text-sm font-bold px-3 py-1.5 rounded-lg border border-slate-700">
                                ${mode.mode_name}
                            </span>
                            
                            <div class="flex items-center bg-slate-800/80 px-3 py-1 rounded-lg border border-slate-700" title="Confidence Score">
                                <i class="fas fa-chart-line ${scoreColor} mr-2 text-sm"></i>
                                <span class="${scoreColor} font-bold">${mode.confidence_score}/100</span>
                            </div>
                        </div>

                        <div class="bg-slate-900/50 rounded-xl p-5 mb-5 border border-slate-700/50">
                            <p id="msg_${mode.mode_id}" class="text-lg text-white leading-relaxed font-medium">${mode.message}</p>
                        </div>
                        
                        <!-- Performance Prediction -->
                        <div class="flex justify-between items-center bg-slate-800/40 rounded-lg p-3 mb-5 border border-slate-700/50">
                            <div class="flex items-center text-sm">
                                <i class="fas fa-mouse-pointer text-slate-400 mr-2"></i>
                                <span class="text-slate-400 mr-2">Expected CTR:</span>
                                <span class="text-blue-400 font-bold">${mode.expected_ctr}</span>
                            </div>
                            <div class="flex items-center text-sm">
                                <i class="fas fa-filter text-slate-400 mr-2"></i>
                                <span class="text-slate-400 mr-2">Conversion:</span>
                                <span class="text-green-400 font-bold">${mode.expected_conversion}</span>
                            </div>
                        </div>

                        <div class="space-y-4">
                            <div>
                                <h4 class="text-xs text-slate-400 uppercase tracking-wider font-semibold mb-2">AI Reasoning</h4>
                                <p class="text-sm text-slate-300 bg-slate-800/30 p-3 rounded-lg border border-slate-700/30 leading-relaxed font-mono text-xs">
                                    ${mode.reasoning}
                                </p>
                            </div>
                            
                            <div class="flex justify-between items-end mt-4">
                                <div class="flex flex-wrap gap-2">
                                    ${tagsHTML}
                                </div>
                                <button onclick="copyToClipboard('msg_${mode.mode_id}')" class="text-sm bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-2 rounded-lg transition-colors border border-slate-600 flex items-center shrink-0 ml-4">
                                    <i class="far fa-copy mr-2"></i> Copy
                                </button>
                            </div>
                        </div>
                    </div>
                `;
                grid.innerHTML += cardHTML;
            });

            // Show results
            setTimeout(() => {
                loadingState.classList.add('hidden');
                resultsState.classList.remove('hidden');
                resultsState.classList.add('fade-in');
            }, 600); // Small artificial delay to show loader and make it feel like AI is "thinking"

        } catch (error) {
            console.error('Error:', error);
            alert('Failed to generate messages. Please make sure the backend is running.');
            loadingState.classList.add('hidden');
            emptyState.classList.remove('hidden');
        }
    });
});

// Clipboard utility
window.copyToClipboard = function(elementId) {
    const text = document.getElementById(elementId).innerText;
    navigator.clipboard.writeText(text).then(() => {
        const toast = document.getElementById('toast');
        toast.classList.remove('translate-y-20', 'opacity-0');
        
        setTimeout(() => {
            toast.classList.add('translate-y-20', 'opacity-0');
        }, 2000);
    });
};
