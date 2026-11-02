# -*- coding: utf-8 -*-
"""节点默认记忆包：项目说明 + 常见问题，保证新节点开箱可用。"""
DOCS = [
    "OpenNetAgent 把每台电脑当成图上的一个节点：节点持有本地记忆与技能，协调者通过 WebSocket 分发任务、聚合结果并做验证。",
    "加入节点只需要一条命令：curl -fsSL <coordinator>/install.sh | bash -s -- --coordinator <coordinator> --token <token>。",
    "节点只建立出站连接，不开放入站端口；使用 nice 19 低优先级，空闲时才工作，不会影响正常工作。",
    "节点可以随时暂停：bash install.sh --pause；恢复：--resume；卸载：--uninstall，会删除服务与目录。",
    "默认 lite 配置不需要本地大模型：只启用 retrieval 与 echo 技能，任何能跑 Python3 的电脑都能加入。",
    "如果机器内存足够且安装了 transformers/torch，可以启用 nli 技能，对 claim 与证据做支持/反驳判断。",
    "本地记忆默认来自协调者分发的 starter 记忆包；也可以把自己的文档目录接入，作为节点私有的检索语料。",
    "协调者按技能路由任务：只会把 retrieval 任务分给声明了 retrieval 的节点，把 nli 任务分给声明了 nli 的节点。",
    "quorum 表示至少多少个节点返回才聚合；quorum 小于节点总数可以在丢包/掉线时自动降级。",
    "路由使用信誉与探索：高成功率节点优先，但低 pull 次数节点仍有被探索的机会。",
    "所有任务与结果写入 SQLite 审计表，可通过 /audit 查询；公网部署应开启 HTTPS、强 token 与限流。",
    "节点返回的结果包含 answer、score 与 evidence；协调者按分数聚合，并可用验证器复核。",
    "OpenNetAgent 不是字面意义的巨大神经网络，而是图上的专家网络：节点是能力单元，边是消息，聚合是注意力。",
    "如果你只有一台普通笔记本，也可以加入：lite 模式只占用很小的 CPU 与内存，且可随时暂停。",
    "项目主页：https://zacrisy.github.io/open-net-agent/ ；代码：https://github.com/zacrisy/open-net-agent 。",
]
