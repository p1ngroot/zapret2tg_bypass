--[[
Zapret2 Telegram Anti-DPI Module
Специализированные функции для обхода блокировок Telegram

Использование:
--lua-init=@telegram.lua
--lua-desync=telegram_bypass
--]]

-- Стандартные импорты из zapret-lib.lua и zapret-antidpi.lua
-- Предполагается что они загружены ранее

-- Конфигурация Telegram
local TELEGRAM_HOSTS = {
    "telegram.org",
    "t.me",
    "telegram.me",
    "tg.dev",
    "telegram-cdn.org",
    "telesco.pe",
    "tgraph.io"
}

-- Порты Telegram
local TELEGRAM_TCP_PORTS = {443, 80, 88, 8080, 8443}
local TELEGRAM_UDP_PORTS = {443, 3478, 3479, 3480, 3481, 5222, 5223, 5224, 8888, 9898, 9899, 9900}

-- MTProto специфичные параметры
local MTProto = {
    initial_packet_pattern = "\x00\x00\x00\x00",  -- Первые 4 байта MTProto
    dc_ips = {}  -- IP адреса дата-центров Telegram
}

-- Функция проверки является ли хост Telegram
function is_telegram_host(hostname)
    if not hostname then return false end
    hostname = hostname:lower()
    for _, host in ipairs(TELEGRAM_HOSTS) do
        if hostname == host or hostname:endswith("." .. host) then
            return true
        end
    end
    return false
end

-- Функция проверки MTProto пакета
function is_mtproto_packet(payload)
    if not payload or #payload < 4 then return false end
    -- Проверяем первые байты на паттерн MTProto
    local first_byte = payload:byte(1)
    -- MTProto использует различные префиксы в зависимости от типа пакета
    return first_byte == 0x00 or first_byte == 0x7f or first_byte == 0x6e
end

-- Основная функция обхода для Telegram
function telegram_bypass(ctx, desync)
    -- Проверка что это TCP трафик
    if not desync.dis.tcp then
        if not desync.dis.icmp then
            instance_cutoff_shim(ctx, desync)
        end
        return
    end
    
    -- Проверка направления - работаем только с исходящим
    direction_cutoff_opposite(ctx, desync, "out")
    if not direction_check(desync, "out") then
        return
    end
    
    -- Проверка хоста если есть track
    local hostname = desync.track and desync.track.hostname
    if hostname and not is_telegram_host(hostname) then
        instance_cutoff_shim(ctx, desync)
        return
    end
    
    -- Применяем стратегии в зависимости от типа трафика
    if desync.l7payload == "tls_client_hello" then
        return telegram_tls_bypass(ctx, desync)
    elseif desync.l7payload == "mtproto_initial" then
        return telegram_mtproto_bypass(ctx, desync)
    elseif desync.l7payload == "http_req" then
        return telegram_http_bypass(ctx, desync)
    end
    
    -- Для неизвестных пейлоадов применяем базовую стратегию
    return telegram_generic_bypass(ctx, desync)
end

-- Обход для TLS трафика Telegram
function telegram_tls_bypass(ctx, desync)
    DLOG("telegram_tls_bypass: applying TLS bypass")
    
    -- Стратегия 1: Fake TLS с повторами
    local fake_opts = {
        blob = "fake_default_tls",
        badsum = true,
        repeats = 2
    }
    
    -- Применяем fake
    if replay_first(desync) then
        local fake_payload = blob(desync, fake_opts.blob)
        if fake_payload then
            -- Применяем модификации
            apply_fooling(desync, nil, {badsum = true})
            apply_ip_id(desync, nil, {ip_id = "seq"})
            
            -- Отправляем фейк
            rawsend_payload_segmented(desync, fake_payload, 0, {
                rawsend = {repeats = fake_opts.repeats},
                fooling = {badsum = true}
            })
            
            DLOG("telegram_tls_bypass: fake sent")
        end
    end
    
    -- Стратегия 2: Multisplit для разделения TLS handshake
    if desync.reasm_data then
        local data = desync.reasm_data
        local pos = resolve_pos(data, "tls_client_hello", "host")
        
        if pos and pos > 1 and pos < #data then
            DLOG("telegram_tls_bypass: splitting at pos " .. pos)
            
            -- Отправляем первую часть
            local part1 = data:sub(1, pos - 1)
            rawsend_payload_segmented(desync, part1, 0, {
                fooling = {tcp_ts_up = true},
                rawsend = {repeats = 1}
            })
            
            -- Отправляем вторую часть
            local part2 = data:sub(pos)
            rawsend_payload_segmented(desync, part2, pos - 1, {
                fooling = {badsum = true},
                rawsend = {repeats = 1}
            })
            
            replay_drop_set(desync)
            return VERDICT_DROP
        end
    end
    
    return VERDICT_PASS
end

-- Обход для MTProto трафика
function telegram_mtproto_bypass(ctx, desync)
    DLOG("telegram_mtproto_bypass: applying MTProto bypass")
    
    -- Стратегия: Изменение длины UDP пакетов
    if desync.dis.udp then
        local payload = desync.dis.payload
        if payload and #payload > 0 then
            -- Немного изменяем длину пакета
            local increment = 2
            local pattern = "\x00"
            
            desync.dis.payload = payload .. pattern:rep(increment)
            DLOG("telegram_mtproto_bypass: length modified " .. #payload .. " => " .. #desync.dis.payload)
            return VERDICT_MODIFY
        end
    end
    
    return VERDICT_PASS
end

-- Обход для HTTP трафика Telegram
function telegram_http_bypass(ctx, desync)
    DLOG("telegram_http_bypass: applying HTTP bypass")
    
    -- Стратегия: Изменение регистра Host заголовка
    if desync.l7payload == "http_req" then
        local hdis = http_dissect_req(desync.dis.payload)
        if hdis then
            local idx_host = array_field_search(hdis.headers, "header_low", "host")
            if idx_host then
                local host = hdis.headers[idx_host]
                local new_host = ""
                
                -- Чередование регистра
                for i = 1, #host.value do
                    local c = host.value:sub(i, i)
                    if i % 2 == 0 then
                        new_host = new_host .. c:lower()
                    else
                        new_host = new_host .. c:upper()
                    end
                end
                
                DLOG("telegram_http_bypass: Host case modified: " .. host.value .. " => " .. new_host)
                
                -- Реконструируем запрос
                hdis.headers[idx_host].value = new_host
                local new_http = http_reconstruct_req(hdis)
                
                if #new_http == #desync.dis.payload then
                    desync.dis.payload = new_http
                    return VERDICT_MODIFY
                end
            end
        end
    end
    
    return VERDICT_PASS
end

-- Базовый обход для любого трафика Telegram
function telegram_generic_bypass(ctx, desync)
    DLOG("telegram_generic_bypass: applying generic bypass")
    
    -- Применяем комбинацию техник
    
    -- 1. Изменение TTL для IPv4
    if desync.dis.ip then
        desync.dis.ip.ip_ttl = 58  -- Чуть меньше стандартного 64
        DLOG("telegram_generic_bypass: TTL modified to 58")
    end
    
    -- 2. Изменение HL для IPv6
    if desync.dis.ip6 then
        desync.dis.ip6.ip6_hlim = 58
        DLOG("telegram_generic_bypass: HL modified to 58")
    end
    
    -- 3. Добавление TCP опций если есть TCP
    if desync.dis.tcp then
        -- Проверяем есть ли SYN
        if bitand(desync.dis.tcp.th_flags, TH_SYN) == TH_SYN then
            DLOG("telegram_generic_bypass: SYN packet detected")
        end
    end
    
    return VERDICT_MODIFY
end

-- Функция для автоматического обнаружения блокировок Telegram
function telegram_auto_detect(ctx, desync)
    if not desync.track then return end
    
    local key = "telegram_auto_" .. (desync.track.hostname or "unknown")
    
    -- Считаем неудачи
    if not desync.track.lua_state[key] then
        desync.track.lua_state[key] = {
            failures = 0,
            last_failure = 0,
            strategy_index = 1
        }
    end
    
    local state = desync.track.lua_state[key]
    local now = clock_getfloattime()
    
    -- Сброс счетчика если прошло много времени
    if now - state.last_failure > 60 then
        state.failures = 0
    end
    
    -- Детекция неудачи (ретрансмиссии, RST, таймауты)
    if is_retransmission(desync) then
        state.failures = state.failures + 1
        state.last_failure = now
        DLOG("telegram_auto_detect: failure detected, count=" .. state.failures)
        
        if state.failures >= 3 then
            -- Переключаем стратегию
            state.strategy_index = (state.strategy_index % 3) + 1
            state.failures = 0
            DLOG("telegram_auto_detect: switching to strategy " .. state.strategy_index)
        end
    end
    
    -- Детекция удачи (успешная передача данных)
    if desync.track.pos and desync.track.pos.direct then
        if desync.track.pos.direct.pcounter > 10 then
            state.failures = 0  -- Сброс при успехе
        end
    end
end

-- Функция для обхода с автоматическим выбором стратегии
function telegram_smart_bypass(ctx, desync)
    -- Сначала пытаемся определить тип трафика
    telegram_auto_detect(ctx, desync)
    
    -- Получаем текущую стратегию из состояния
    local strategy = 1
    if desync.track and desync.track.lua_state then
        local key = "telegram_auto_" .. (desync.track.hostname or "unknown")
        if desync.track.lua_state[key] then
            strategy = desync.track.lua_state[key].strategy_index
        end
    end
    
    DLOG("telegram_smart_bypass: using strategy " .. strategy)
    
    -- Применяем стратегию
    if strategy == 1 then
        return telegram_tls_bypass(ctx, desync)
    elseif strategy == 2 then
        return telegram_generic_bypass(ctx, desync)
    else
        return telegram_mtproto_bypass(ctx, desync)
    end
end

-- Утилита для проверки окончания строки
if not string.endswith then
    function string.endswith(str, ending)
        return str:sub(-#ending) == ending
    end
end

-- Экспорт функций
return {
    telegram_bypass = telegram_bypass,
    telegram_tls_bypass = telegram_tls_bypass,
    telegram_mtproto_bypass = telegram_mtproto_bypass,
    telegram_http_bypass = telegram_http_bypass,
    telegram_generic_bypass = telegram_generic_bypass,
    telegram_auto_detect = telegram_auto_detect,
    telegram_smart_bypass = telegram_smart_bypass,
    is_telegram_host = is_telegram_host,
    is_mtproto_packet = is_mtproto_packet
}
