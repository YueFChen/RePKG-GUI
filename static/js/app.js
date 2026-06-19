/**
 * RePKG-GUI Alpine.js 应用逻辑
 * 深色液态玻璃风格
 * 性能优化版本
 */

function repkgApp() {
    return {
        // 状态
        isRunning: false,
        eventSource: null,
        pollInterval: null,
        scanDebounceTimer: null,

        // 用户配置
        config: {
            inputPath: '',
            outputPath: '',
            repkgPath: './static/assets/RePKG.exe',
            options: {
                convertTex: true,
                copyProject: true,
                overwrite: false,
                recursive: true,
                copyPreview: true
            },
            appearance: {
                backgroundImage: '',
                backgroundOpacity: 0.15,
                backgroundBlur: 0
            }
        },

        // Steam 检测路径
        steamConfig: {
            inputPath: '',
            outputPath: ''
        },

        // 文件列表
        pkgFiles: [],

        // 输出目录文件列表
        outputFiles: [],
        activeView: 'input',  // 'input' | 'output'

        // 搜索和筛选
        searchQuery: '',
        filterType: 'all',  // 'all' | 'scene' | 'video' | 'web' | 'application'

        // 多选
        selectedFiles: new Set(),

        // 右键菜单
        contextMenu: {
            show: false,
            x: 0,
            y: 0,
            file: null
        },

        // 视频播放模态框
        videoModal: {
            show: false,
            title: '',
            path: ''
        },

        // 日志
        logs: [],
        progress: {
            current: 0,
            total: 0,
            percentage: 0,
            current_file: ''
        },

        // 计算属性
        get canExtract() {
            return this.config.inputPath &&
                   this.config.outputPath &&
                   this.pkgFiles.length > 0 &&
                   !this.isRunning;
        },

        get currentFiles() {
            return this.activeView === 'output' ? this.outputFiles : this.pkgFiles;
        },

        get filteredFiles() {
            let files = this.currentFiles;
            // 类型筛选
            if (this.filterType !== 'all') {
                files = files.filter(f => {
                    const typeMap = { scene: 'is_scene', video: 'is_video', web: 'is_web', application: 'is_application' };
                    return f[typeMap[this.filterType]];
                });
            }
            // 文本搜索（匹配名称、标题、workshop_id）
            if (this.searchQuery.trim()) {
                const q = this.searchQuery.trim().toLowerCase();
                files = files.filter(f => {
                    return (f.name || '').toLowerCase().includes(q)
                        || (f.title || '').toLowerCase().includes(q)
                        || (f.workshop_id || '').toLowerCase().includes(q);
                });
            }
            return files;
        },

        get isAllSelected() {
            return this.filteredFiles.length > 0 && this.filteredFiles.every(f => this.selectedFiles.has(f.dir_path));
        },

        get hasSelection() {
            return this.selectedFiles.size > 0;
        },

        // 初始化
        async init() {
            // 先加载用户配置
            await this.loadConfig();
            // 加载背景图片列表
            this.loadBackgrounds();
            // 自动检测 Steam 路径
            await this.detectSteamPaths();
            // 合并路径：优先使用用户配置，没有则使用 Steam 检测路径
            if (!this.config.inputPath && this.steamConfig.inputPath) {
                this.config.inputPath = this.steamConfig.inputPath;
            }
            if (!this.config.outputPath && this.steamConfig.outputPath) {
                this.config.outputPath = this.steamConfig.outputPath;
            }
            // 如果有输入路径，自动扫描
            if (this.config.inputPath) {
                await this.scanFiles();
            }
        },

        // 加载配置
        async loadConfig() {
            try {
                const response = await fetch('/api/settings');
                const data = await response.json();
                if (data.success && data.data) {
                    // 加载用户配置
                    if (data.data.user) {
                        this.config = this.mergeDeep(this.config, data.data.user);
                    }
                    // 加载 Steam 检测路径
                    if (data.data.steam) {
                        this.steamConfig = data.data.steam;
                    }
                }
            } catch (error) {
                console.error('加载配置失败:', error);
            }
        },

        // 扫描文件（带防抖）
        async scanFiles() {
            // 清除之前的防抖定时器
            if (this.scanDebounceTimer) {
                clearTimeout(this.scanDebounceTimer);
            }

            // 延迟 300ms 执行，避免频繁请求
            this.scanDebounceTimer = setTimeout(async () => {
                await this._doScan();
            }, 300);
        },

        // 实际扫描操作
        async _doScan() {
            if (!this.config.inputPath) {
                this.pkgFiles = [];
                return;
            }

            try {
                const response = await fetch(
                    `/api/scan?path=${encodeURIComponent(this.config.inputPath)}&recursive=${this.config.options.recursive}`
                );
                const data = await response.json();
                if (data.success) {
                    this.pkgFiles = data.data.files || [];
                    notify(`发现 ${this.pkgFiles.length} 个项目`, 'info');
                }
            } catch (error) {
                console.error('扫描文件失败:', error);
                this.pkgFiles = [];
            }
        },

        // 刷新文件列表
        async refreshFiles() {
            if (this.isRunning) return;

            // 清除缓存，重新扫描
            try {
                // 先清除缓存
                await fetch('/api/cache/clear', { method: 'POST' });
                // 重新扫描
                await this._doScan();
                notify('已刷新项目列表', 'success');
            } catch (error) {
                console.error('刷新失败:', error);
                notify('刷新失败', 'error');
            }
        },

        // 自动检测 Steam 路径
        async detectSteamPaths() {
            try {
                const response = await fetch('/api/steam/detect');
                const data = await response.json();
                if (data.success && data.data) {
                    // 保存到 steamConfig（不自动填充用户配置）
                    this.steamConfig.inputPath = data.data.workshop_path || '';
                    this.steamConfig.outputPath = data.data.wallpaper_projects_my || '';
                }
            } catch (error) {
                console.error('检测 Steam 路径失败:', error);
            }
        },

        // 浏览目录
        browseDirectory(type) {
            // 优先使用 File System Access API
            if ('showDirectoryPicker' in window) {
                this._browseWithAPI(type);
            } else {
                // 降级方案：使用 webkitdirectory input
                this._browseWithInput(type);
            }
        },

        // 使用 File System Access API（现代浏览器）
        async _browseWithAPI(type) {
            try {
                const dirHandle = await window.showDirectoryPicker();
                const path = dirHandle.name;

                // 注意：File System Access API 不允许直接获取完整路径
                // 需要用户手动输入完整路径或使用其他方式
                // 这里使用 name 作为显示名，实际路径需要另外处理
                if (type === 'input') {
                    // 由于 API 限制，使用提示让用户输入完整路径
                    const fullPath = prompt('请输入所选目录的完整路径:', dirHandle.name);
                    if (fullPath) {
                        this.config.inputPath = fullPath;
                        this.saveConfig();
                        this.scanFiles();
                    }
                } else {
                    const fullPath = prompt('请输入所选目录的完整路径:', dirHandle.name);
                    if (fullPath) {
                        this.config.outputPath = fullPath;
                        this.saveConfig();
                    }
                }
            } catch (err) {
                if (err.name !== 'AbortError') {
                    console.error('目录选择失败:', err);
                }
            }
        },

        // 使用 webkitdirectory input（兼容方案）
        _browseWithInput(type) {
            // 设置当前选择的类型
            this._currentDirType = type;

            // 触发文件输入
            const input = document.getElementById('dirPicker');
            if (input) {
                // 对于输出目录，降级为文本输入
                if (type === 'output') {
                    const path = prompt('请输入输出目录路径:');
                    if (path) {
                        this.config.outputPath = path;
                        this.saveConfig();
                    }
                    return;
                }
                input.click();
            }
        },

        // 处理目录选择结果
        handleDirSelect(event) {
            const files = event.target.files;
            if (files && files.length > 0) {
                // 获取第一个文件的父目录作为输入目录
                const firstFile = files[0];
                let dirPath = firstFile.webkitRelativePath.split('/')[0];

                // 如果是相对路径，需要拼接
                if (!dirPath || dirPath === '.') {
                    // 使用 path 获取实际路径（如果浏览器提供）
                    dirPath = firstFile.mozFullPath || firstFile.webkitRelativePath || firstFile.name;
                    // 尝试获取目录路径
                    const lastSep = firstFile.webkitRelativePath.lastIndexOf('/');
                    if (lastSep > 0) {
                        dirPath = firstFile.webkitRelativePath.substring(0, lastSep);
                    }
                }

                // 尝试从文件对象获取完整路径
                const filePath = firstFile.webkitRelativePath || firstFile.mozFullPath || '';
                const pathParts = filePath.split('/');
                if (pathParts.length > 1) {
                    // 去掉文件名，保留目录路径
                    pathParts.pop();
                    dirPath = pathParts.join('/');
                }

                if (dirPath && dirPath !== '.') {
                    this.config.inputPath = dirPath;
                    this.saveConfig();
                    this.scanFiles();
                }
            }
            // 清空 input 以允许重新选择相同目录
            event.target.value = '';
        },

        // ========== 视图切换 ==========

        switchView(view) {
            if (view === this.activeView) return;
            this.activeView = view;
            this.selectedFiles = new Set();
            this.searchQuery = '';
            this.filterType = 'all';
            if (view === 'output' && this.config.outputPath) {
                this.scanOutput();
            } else if (view === 'input' && this.config.inputPath) {
                this.scanFiles();
            }
        },

        // ========== 输出目录管理 ==========

        async scanOutput() {
            if (!this.config.outputPath) return;
            try {
                const response = await fetch('/api/output/scan', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ outputPath: this.config.outputPath })
                });
                const data = await response.json();
                if (data.success) {
                    this.outputFiles = data.data.files || [];
                }
            } catch (error) {
                console.error('扫描输出目录失败:', error);
                this.outputFiles = [];
            }
        },

        async refreshOutput() {
            // 清除缓存
            try {
                await fetch('/api/cache/clear', { method: 'POST' });
                await this.scanOutput();
                notify('已刷新输出项目列表', 'success');
            } catch (error) {
                console.error('刷新输出失败:', error);
            }
        },

        async deleteSelectedProjects() {
            const paths = Array.from(this.selectedFiles);
            if (paths.length === 0) return;
            if (this.isRunning) return;

            const count = paths.length;
            if (!confirm(`确定要删除选中的 ${count} 个项目吗？\n\n此操作不可撤销。`)) return;

            try {
                const response = await fetch('/api/output/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ dirPaths: paths })
                });
                const data = await response.json();
                if (data.success) {
                    notify(`成功删除 ${data.data.deleted} 个项目` + (data.data.failed > 0 ? `，${data.data.failed} 个失败` : ''), 'success');
                    this.selectedFiles = new Set();
                    await this.scanOutput();
                } else {
                    notify('删除失败: ' + data.error, 'error');
                }
            } catch (error) {
                console.error('删除项目失败:', error);
                notify('删除项目失败', 'error');
            }
        },

        deleteSingleProject(dirPath) {
            this.deselectAll();
            this.selectedFiles.add(dirPath);
            this.selectedFiles = new Set(this.selectedFiles);
            this.deleteSelectedProjects();
        },

        // ========== 选择 / 右键菜单 ==========

        toggleSelect(dirPath) {
            if (this.selectedFiles.has(dirPath)) {
                this.selectedFiles.delete(dirPath);
            } else {
                this.selectedFiles.add(dirPath);
            }
            // 触发 Alpine 响应式更新
            this.selectedFiles = new Set(this.selectedFiles);
        },

        selectAll() {
            this.filteredFiles.forEach(f => this.selectedFiles.add(f.dir_path));
            this.selectedFiles = new Set(this.selectedFiles);
        },

        deselectAll() {
            this.selectedFiles = new Set();
        },

        // 右键菜单
        showContextMenu(event, file) {
            this.contextMenu = {
                show: true,
                x: event.clientX,
                y: event.clientY,
                file: file
            };
            // 点击其他地方关闭
            const self = this;
            setTimeout(() => {
                const handler = () => {
                    self.contextMenu = { show: false, x: 0, y: 0, file: null };
                    document.removeEventListener('click', handler);
                };
                document.addEventListener('click', handler, { once: true });
            }, 0);
        },

        contextSelectSingle() {
            const file = this.contextMenu.file;
            if (file) {
                this.deselectAll();
                this.selectedFiles.add(file.dir_path);
                this.selectedFiles = new Set(this.selectedFiles);
            }
            this.contextMenu = { show: false, x: 0, y: 0, file: null };
        },

        contextExtractSingle() {
            const file = this.contextMenu.file;
            this.contextMenu = { show: false, x: 0, y: 0, file: null };
            if (file) {
                this.extractTargets([file.dir_path]);
            }
        },

        contextOpenLocation() {
            const file = this.contextMenu.file;
            this.contextMenu = { show: false, x: 0, y: 0, file: null };
            if (file) {
                this.openLocation(file.dir_path || file.path);
            }
        },

        contextDeleteSingle() {
            const file = this.contextMenu.file;
            this.contextMenu = { show: false, x: 0, y: 0, file: null };
            if (file) {
                this.deleteSingleProject(file.dir_path);
            }
        },

        // 提取选中项目
        extractSelected() {
            if (this.selectedFiles.size === 0) return;
            this.extractTargets(Array.from(this.selectedFiles));
        },

        extractTargets(targetPaths) {
            if (this.isRunning || !this.config.inputPath || !this.config.outputPath) return;
            if (targetPaths.length === 0) return;

            this.logs = [];
            this.progress = { current: 0, total: 0, percentage: 0, current_file: '' };

            fetch('/api/extract', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    inputPath: this.config.inputPath,
                    outputPath: this.config.outputPath,
                    repkgPath: this.config.repkgPath,
                    options: this.config.options,
                    targets: targetPaths
                })
            }).then(response => response.json()).then(data => {
                if (data.success) {
                    this.isRunning = true;
                    this.addLog('info', `提取任务已启动 (${targetPaths.length} 个项目)`);
                    notify('提取任务已启动', 'info');
                    this.startPolling();
                } else {
                    notify('启动失败: ' + data.error, 'error');
                }
            }).catch(error => {
                console.error('启动提取失败:', error);
                notify('启动提取失败', 'error');
            });
        },

        // 防抖搜索
        onSearchInput() {
            // 搜索时清除选择
            if (this.searchDebounceTimer) clearTimeout(this.searchDebounceTimer);
            this.searchDebounceTimer = setTimeout(() => {}, 150);
        },

        // ========== 提取控制 ==========

        // 开始提取
        async startExtract() {
            if (this.isRunning || !this.canExtract) return;

            this.logs = [];
            this.progress = { current: 0, total: 0, percentage: 0, current_file: '' };

            try {
                const response = await fetch('/api/extract', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        inputPath: this.config.inputPath,
                        outputPath: this.config.outputPath,
                        repkgPath: this.config.repkgPath,
                        options: this.config.options
                    })
                });

                const data = await response.json();
                if (data.success) {
                    this.isRunning = true;
                    this.addLog('info', '提取任务已启动...');
                    notify('提取任务已启动', 'info');
                    this.startPolling();
                } else {
                    notify('启动失败: ' + data.error, 'error');
                }
            } catch (error) {
                console.error('启动提取失败:', error);
                notify('启动提取失败', 'error');
            }
        },

        // 停止提取
        async stopExtract() {
            try {
                await fetch('/api/stop', { method: 'POST' });
                this.isRunning = false;
                this.stopPolling();
                this.addLog('warning', '任务已停止');
                notify('任务已停止', 'warning');
            } catch (error) {
                console.error('停止任务失败:', error);
            }
        },

        // 打开文件所在位置
        async openLocation(path) {
            try {
                const response = await fetch('/api/open_location', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path })
                });
                const data = await response.json();
                if (!data.success) {
                    notify('打开位置失败: ' + data.error, 'error');
                }
            } catch (error) {
                console.error('打开位置失败:', error);
                notify('打开位置失败', 'error');
            }
        },

        // 选择 RePKG.exe 路径
        pickRepkgFile() {
            const input = document.getElementById('repkgFilePicker');
            if (input) {
                input.click();
            }
        },

        handleRepkgFileSelect(event) {
            const files = event.target.files;
            if (files && files.length > 0) {
                this.config.repkgPath = files[0].name;
                this.saveConfig();
                notify('RePKG 路径已更新: ' + files[0].name, 'success');
            }
            event.target.value = '';
        },

        // 背景图片列表
        backgrounds: [],

        // 选择背景图片
        pickBackgroundImage() {
            const input = document.getElementById('bgImagePicker');
            if (input) {
                input.click();
            }
        },

        handleBgImageSelect(event) {
            const file = event.target.files?.[0];
            if (!file) return;
            if (!file.type.startsWith('image/')) {
                notify('请选择图片文件', 'warning');
                event.target.value = '';
                return;
            }
            this._uploadBackground(file);
            event.target.value = '';
        },

        async _uploadBackground(file) {
            const formData = new FormData();
            formData.append('file', file);
            try {
                const res = await fetch('/api/backgrounds/upload', { method: 'POST', body: formData });
                const data = await res.json();
                if (data.success) {
                    this.config.appearance.backgroundImage = data.data.filename;
                    this.saveConfig();
                    await this.loadBackgrounds();
                    notify('背景图片已上传', 'success');
                } else {
                    notify('上传失败: ' + data.error, 'error');
                }
            } catch (e) {
                notify('上传失败', 'error');
            }
        },

        // 从列表选择背景
        selectBackground(filename) {
            this.config.appearance.backgroundImage = this.config.appearance.backgroundImage === filename ? '' : filename;
            this.saveConfig();
        },

        // 清除背景图片
        clearBackgroundImage() {
            this.config.appearance.backgroundImage = '';
            this.saveConfig();
            notify('背景图片已清除', 'info');
        },

        // 删除背景图片文件
        async deleteBackgroundFile(filename) {
            if (!confirm(`确定要删除背景图片 "${filename}" 吗？`)) return;
            try {
                const res = await fetch('/api/backgrounds/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename })
                });
                const data = await res.json();
                if (data.success) {
                    if (this.config.appearance.backgroundImage === filename) {
                        this.config.appearance.backgroundImage = '';
                        this.saveConfig();
                    }
                    await this.loadBackgrounds();
                    notify('背景图片已删除', 'success');
                } else {
                    notify('删除失败: ' + data.error, 'error');
                }
            } catch (e) {
                notify('删除失败', 'error');
            }
        },

        // 加载背景图片列表
        async loadBackgrounds() {
            try {
                const res = await fetch('/api/backgrounds');
                const data = await res.json();
                if (data.success) {
                    this.backgrounds = data.data || [];
                }
            } catch (e) {
                console.error('加载背景列表失败:', e);
            }
        },

        // 获取当前背景图片 URL
        get backgroundSrc() {
            const bg = this.config.appearance.backgroundImage;
            if (bg) {
                return '/api/background/image/' + encodeURIComponent(bg);
            }
            return '';
        },

        // 保存配置
        async saveConfig() {
            try {
                await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.config)
                });
            } catch (error) {
                console.error('保存配置失败:', error);
            }
        },

        // 轮询获取进度（替代 SSE，更高效）
        startPolling() {
            if (this.pollInterval) return;

            this.pollInterval = setInterval(async () => {
                if (!this.isRunning) {
                    this.stopPolling();
                    return;
                }

                try {
                    const response = await fetch('/api/progress');
                    const data = await response.json();
                    if (data.success && data.data) {
                        const p = data.data;

                        // 更新日志（避免重复添加）
                        if (p.logs && p.logs.length > 0) {
                            // 只添加新的日志（比较最后一条日志的时间戳）
                            const lastLogTime = this.logs.length > 0 ? this.logs[this.logs.length - 1].timestamp : '';
                            let hasNewLogs = false;
                            p.logs.forEach(log => {
                                // log 是 dict 结构: {level, message, detail, timestamp}
                                if (log.timestamp && log.timestamp !== lastLogTime) {
                                    // 检查是否已存在相同时间戳的日志
                                    if (!this.logs.some(l => l.timestamp === log.timestamp && l.message === log.message)) {
                                        this.logs.push({
                                            level: log.level,
                                            message: log.message,
                                            detail: log.detail || '',
                                            timestamp: log.timestamp
                                        });
                                        hasNewLogs = true;
                                    }
                                }
                            });
                            // 限制日志数量
                            if (this.logs.length > 500) {
                                this.logs = this.logs.slice(-500);
                            }
                            // 自动滚动到底部
                            if (hasNewLogs) {
                                this.$nextTick(() => {
                                    const container = this.$refs.logContainer;
                                    if (container) {
                                        container.scrollTop = container.scrollHeight;
                                    }
                                });
                            }
                        }

                        // 更新进度
                        this.progress = {
                            current: 0,
                            total: 0,
                            percentage: p.progress,
                            current_file: p.current
                        };

                        // 检查任务是否结束
                        if (!p.isRunning) {
                            this.isRunning = false;
                            this.stopPolling();
                            this.addLog('success', '提取完成');
                            notify('提取完成', 'success');
                        }
                    }
                } catch (error) {
                    console.error('获取进度失败:', error);
                }
            }, 500); // 每 500ms 轮询一次
        },

        stopPolling() {
            if (this.pollInterval) {
                clearInterval(this.pollInterval);
                this.pollInterval = null;
            }
        },

        // 日志管理
        addLog(level, message) {
            const timestamp = new Date().toLocaleTimeString('zh-CN', { hour12: false });
            this.logs.push({ level, message, timestamp });

            // 限制日志数量，防止内存泄漏
            if (this.logs.length > 200) {
                this.logs = this.logs.slice(-200);
            }

            this.$nextTick(() => {
                const container = this.$refs.logContainer;
                if (container) {
                    container.scrollTop = container.scrollHeight;
                }
            });
        },

        clearLogs() {
            this.logs = [];
        },

        exportLogs() {
            if (this.logs.length === 0) {
                notify('日志为空', 'warning');
                return;
            }

            const content = this.logs
                .map(log => `[${log.timestamp}] ${log.message}`)
                .join('\n');

            const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `RePKG_Log_${new Date().toISOString().slice(0, 10)}.txt`;
            a.click();
            URL.revokeObjectURL(url);

            notify('日志已导出', 'success');
        },

        // 格式化文件大小
        formatSize(size) {
            if (!size) return '0 B';
            const units = ['B', 'KB', 'MB', 'GB'];
            let i = 0;
            while (size >= 1024 && i < units.length - 1) {
                size /= 1024;
                i++;
            }
            return `${size.toFixed(i > 0 ? 1 : 0)} ${units[i]}`;
        },

        // 深度合并对象
        mergeDeep(target, source) {
            const output = { ...target };
            for (const key in source) {
                if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
                    output[key] = this.mergeDeep(target[key] || {}, source[key]);
                } else {
                    output[key] = source[key];
                }
            }
            return output;
        },

        // 视频播放
        playVideo(file) {
            if (!file.video_file) {
                notify('未找到视频文件', 'warning');
                return;
            }
            this.videoModal = {
                show: true,
                title: file.title || file.name,
                path: file.video_file
            };
        },

        closeVideoModal() {
            this.videoModal.show = false;
            this.videoModal.path = '';
        },

        // 清理资源
        destroy() {
            this.stopPolling();
            if (this.eventSource) {
                this.eventSource.close();
            }
            if (this.scanDebounceTimer) {
                clearTimeout(this.scanDebounceTimer);
            }
        }
    };
}
