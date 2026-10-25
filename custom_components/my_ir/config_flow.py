from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol
from .const import DOMAIN
from homeassistant.helpers import selector
import logging
import asyncio
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

# Hardened fork: the upstream options flow downloaded IR code libraries from
# the vendor cloud API. It was removed so this
# integration makes no outbound internet requests.
# 按键控制，喇叭播放，电量，屏幕唤醒集成到HA中，在

class MyIRConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """配置流程 (首次添加集成网关时触发)"""
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """点击集成名称即发送配对请求，无需中间表单"""
        
        # 【关键】确保 WebSocket 处理器已注册（async_setup 可能未被调用）
        from homeassistant.components import websocket_api
        from . import websocket_submit_pair_data, websocket_get_device_codes, websocket_get_harmony_config
        websocket_api.async_register_command(self.hass, websocket_submit_pair_data)
        websocket_api.async_register_command(self.hass, websocket_get_device_codes)
        websocket_api.async_register_command(self.hass, websocket_get_harmony_config)
        _LOGGER.info("[config_flow] WebSocket handler registered during config flow")
        
        # 开始新配对前，清理上次残留的发现列表
        self.hass.data.setdefault(DOMAIN, {}).pop("discovered_gateways", None)
        
        # 直接发出配对广播
        self.hass.bus.async_fire(f"{DOMAIN}/pair_request", {
            "code": "DISCOVER_ALL",
            "mode": "discover_all",
            "timestamp": datetime.utcnow().isoformat(),
            "source": "config_flow"
        })
        _LOGGER.info(
            "[Pair] Broadcast pair_request event (%s/pair_request), waiting 8s for App response… "
            "Please ensure App is logged in and connected to HA via WebSocket", DOMAIN
        )
        
        # 等待 8 秒让 App 响应
        await asyncio.sleep(8)
        
        discovered = self.hass.data.get(DOMAIN, {}).get("discovered_gateways", {})
        _LOGGER.info("Discovered %d gateways after 5s: %s", len(discovered), list(discovered.keys()))
        
        # 进入发现步骤
        return await self.async_step_discover()

    async def async_step_discover(self, user_input: dict | None = None) -> FlowResult:
        """显示已发现的网关列表，或重试搜索"""
        discovered = self.hass.data.get(DOMAIN, {}).get("discovered_gateways", {})

        if user_input is not None:
            selected_serial = user_input.get("gateway")
            if selected_serial and selected_serial in discovered:
                gw_data = discovered[selected_serial]
                model = gw_data.get("model", "IR Gateway")
                # 创建条目，填入 App 信息
                return self.async_create_entry(
                    title=f"Smart Remote:{model} SN:{selected_serial}",
                    data={
                        "app_serial": selected_serial,
                        "app_model": model
                    }
                )

        _LOGGER.info("[discover] Final check — discovered_gateways=%s, len=%d", dict(discovered), len(discovered))
        
        # 检查是否有发现的网关
        if discovered:
            _LOGGER.info("[discover] Gateways found! Showing selection list, count=%d", len(discovered))
            options = [
                {"value": s, "label": f"Smart Remote:{d.get('model','IR Gateway')} SN:{s}"}
                for s, d in discovered.items()
            ]
            return self.async_show_form(
                step_id="discover",
                data_schema=vol.Schema({
                    vol.Required("gateway"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options, mode="list")
                    )
                }),
                description_placeholders={
                    "count": str(len(discovered))
                }
            )
        else:
            _LOGGER.info("[discover] No gateways found, showing retry screen")
            # 无发现，显示重试界面
            return self.async_show_form(
                step_id="discover_retry",
                data_schema=vol.Schema({
                    vol.Optional("retry", default=False): selector.BooleanSelector(
                        selector.BooleanSelectorConfig()
                    )
                })
            )

    async def async_step_discover_retry(self, user_input: dict | None = None) -> FlowResult:
        """处理重试表单的提交——重新广播发现"""
        if user_input is None:
            return self.async_show_form(
                step_id="discover_retry",
                data_schema=vol.Schema({
                    vol.Optional("retry", default=False): selector.BooleanSelector(
                        selector.BooleanSelectorConfig()
                    )
                })
            )

        if user_input.get("retry"):
            self.hass.bus.async_fire(f"{DOMAIN}/pair_request", {
                "code": "DISCOVER_ALL",
                "mode": "discover_all",
                "timestamp": datetime.utcnow().isoformat(),
                "source": "config_flow"
            })
            _LOGGER.info("[Retry] User requested re-discovery, waiting 8s…")
            await asyncio.sleep(8)

            discovered = self.hass.data.get(DOMAIN, {}).get("discovered_gateways", {})
            _LOGGER.info("[Retry] Discovered %d gateways", len(discovered))

            if discovered:
                options = [
                    {"value": s, "label": f"Smart Remote:{d.get('model','IR Gateway')} SN:{s}"}
                    for s, d in discovered.items()
                ]
                return self.async_show_form(
                    step_id="discover",
                    data_schema=vol.Schema({
                        vol.Required("gateway"): selector.SelectSelector(
                            selector.SelectSelectorConfig(options=options, mode="list")
                        )
                    }),
                    description_placeholders={
                        "count": str(len(discovered))
                    }
                )

        # 仍然无发现，或用户未勾选重试——再次显示重试界面
        if not user_input.get("retry"):
            _LOGGER.info("[Retry] User did not check 'Retry', staying on retry screen")
        else:
            _LOGGER.warning("[Retry] No gateways found after retry, please check if App is online")

        return self.async_show_form(
            step_id="discover_retry",
            data_schema=vol.Schema({
                vol.Optional("retry", default=False): selector.BooleanSelector(
                    selector.BooleanSelectorConfig()
                )
            })
        )
