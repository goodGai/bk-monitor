# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import copy
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Dict, List

from bkmonitor.documents.incident import IncidentDocument
from constants.incident import (
    IncidentGraphComponentType,
    IncidentGraphEdgeEventDirection,
    IncidentGraphEdgeEventType,
    IncidentGraphEdgeType,
)
from core.drf_resource import api
from core.errors.incident import IncidentEntityNotFoundError


@dataclass
class IncidentGraphCategory:
    """
    "category_id": 2,
    "category_name": "data_center",
    "category_alias": "数据中心"
    """

    category_id: int
    category_name: str
    category_alias: str

    def to_src_dict(self):
        return asdict(self)


@dataclass
class IncidentGraphRank:
    """
    "rank_id": 0,
    "rank_name": "service_module",
    "rank_alias": "服务模块",
    "rank_category": "service"
    """

    rank_id: int
    rank_name: str
    rank_alias: str
    rank_category: IncidentGraphCategory

    def to_src_dict(self):
        data = asdict(self)
        data["rank_category"] = data.pop("rank_category")["category_name"]
        return data


@dataclass
class IncidentGraphEntity:
    """
    "entity_id": "BCS-K8S-xxxx#k8s-idc-br#uid-0",
    "entity_name": "BCS-K8S-xxxx#k8s-idc-br#uid-0",
    "entity_type": "BcsPod",
    "is_anomaly": false,
    "anomaly_score": 0.3333333333333333,
    "anomaly_type": "死机/重启",
    "is_root": false,
    "is_on_alert": false,
    "bk_biz_id": None,
    "product_hierarchy_rank": "rank_0"
    "dimensions": {
        "node_type": "BcsPod",
        "cluster_id": "BCS-K8S-xxxx",
        "namespace": "k8s-xxxxx-trunk",
        "pod_name": "uid-0"
    },
    "tags": {}
    """

    entity_id: str
    entity_name: str
    entity_type: str
    is_anomaly: bool
    is_root: bool
    rank: IncidentGraphRank
    dimensions: Dict
    anomaly_score: float = 0
    anomaly_type: str = ""
    is_on_alert: bool = False
    bk_biz_id: int = None
    tags: Dict = field(default_factory=dict)
    aggregated_entities: List["IncidentGraphEntity"] = field(default_factory=list)
    component_type: IncidentGraphComponentType = IncidentGraphComponentType.PRIMARY

    def to_src_dict(self):
        data = asdict(self)
        data["rank_name"] = data["rank"]["rank_name"]
        data["component_type"] = self.component_type.value
        return data

    def logic_key(self):
        """用于块划分的逻辑Key"""
        return (self.tags.get("BcsService", {}) or self.tags.get("BcsWorkload", {})).get("name", self.entity_id)

    def logic_content(self):
        """用于块划分的逻辑Key的内容"""
        return self.tags.get("BcsService", {}) or self.tags.get("BcsWorkload", {})


@dataclass
class IncidentGraphEdgeEvent:
    """
    "event_type": "anomaly",
    "event_name": "从属关系异常",
    "event_time": 1713333333,
    "direction": "forward" // "reverse"
    "time_series": [[1713401520000, 0], [1713401520001, 1]]
    "metric_name": "condition.diskAlert"
    """

    event_type: IncidentGraphEdgeEventType
    event_name: str
    event_time: int
    direction: IncidentGraphEdgeEventDirection = IncidentGraphEdgeEventDirection.FORWARD
    time_series: List = field(default_factory=list)
    metric_name: str = ""

    def to_src_dict(self):
        return {
            "event_type": self.event_type.value,
            "event_name": self.event_name,
            "event_time": self.event_time,
            "direction": self.direction.value,
            "time_series": self.time_series,
            "metric_name": self.metric_name,
        }


@dataclass
class IncidentGraphEdge:
    """
    "source_type": "BkNodeHost",
    "target_type": "BcsPod",
    "source_id": "0#xx.xx.xx.xx",
    "target_id": "BCS-K8S-xxxxx#k8s-idc-br#uid-0"
    "events": [
        {
            "event_type": "anomaly",
            "event_name": "从属关系异常",
            "event_time": 1713333333,
            "direction": "forward" // "reverse",
            "time_series": [[1713401520000, 0], [1713401520001, 1]],
            "metric_name": "condition.diskAlert"
        }
    ]
    """

    source: IncidentGraphEntity
    target: IncidentGraphEntity
    edge_type: IncidentGraphEdgeType
    events: List[IncidentGraphEdgeEvent] = field(default_factory=list)
    is_anomaly: bool = False
    anomaly_score: float = 0
    aggregated_edges: List["IncidentGraphEdge"] = field(default_factory=list)
    component_type: IncidentGraphComponentType = IncidentGraphComponentType.PRIMARY

    def to_src_dict(self):
        return {
            "source_type": self.source.entity_type,
            "source": self.source.entity_id,
            "source_name": self.source.entity_name,
            "source_is_anomaly": self.source.is_anomaly,
            "source_is_on_alert": self.source.is_on_alert,
            "count": len(self.aggregated_edges) + 1,
            "aggregated": len(self.aggregated_edges) > 0,
            "target_type": self.target.entity_type,
            "target": self.target.entity_id,
            "target_name": self.target.entity_name,
            "target_is_anomaly": self.target.is_anomaly,
            "target_is_on_alert": self.target.is_on_alert,
            "edge_type": self.edge_type.value,
            "is_anomaly": self.is_anomaly,
            "anomaly_score": self.anomaly_score,
            "events": [event.to_src_dict() for event in self.events],
            "aggregated_edges": [edge.to_src_dict() for edge in self.aggregated_edges],
            "component_type": self.component_type.value,
        }


@dataclass
class IncidentAlert:
    """
    "id": "170191709725733",
    "strategy_id": "25",
    "entity_id": "BCS-K8S-xxxx#k8s-idc-br#uid-0"
    """

    id: int
    strategy_id: int
    entity: IncidentGraphEntity
    alert_status: str = ""
    alert_time: int = None

    def to_src_dict(self):
        data = asdict(self)
        data["entity_id"] = data.pop("entity")["entity_id"]
        return data


@dataclass
class IncidentSnapshot(object):
    """
    用于处理故障根因定位结果快照数据的类.
    """

    incident_snapshot_content: Dict

    def __post_init__(self, prepare: bool = True):
        self.incident_graph_categories = {}
        self.incident_graph_ranks = {}
        self.incident_graph_entities = {}
        self.incident_graph_edges = {}
        self.alert_entity_mapping = {}
        self.bk_biz_id = None
        self.entity_targets = defaultdict(lambda: defaultdict(set))
        self.entity_sources = defaultdict(lambda: defaultdict(set))

        if prepare:
            self.prepare_graph()
            self.prepare_alerts()

    def prepare_graph(self):
        """根据故障分析结果快照实例化图结构."""
        for category_name, category_info in self.incident_snapshot_content["product_hierarchy_category"].items():
            self.incident_graph_categories[category_name] = IncidentGraphCategory(**category_info)

        for rank_name, rank_info in self.incident_snapshot_content["product_hierarchy_rank"].items():
            rank_info["rank_category"] = self.incident_graph_categories[rank_info["rank_category"]]
            self.incident_graph_ranks[rank_name] = IncidentGraphRank(**rank_info)

        for entity_info in self.incident_snapshot_content["incident_propagation_graph"]["entities"]:
            entity_info["rank"] = self.incident_graph_ranks[entity_info.pop("rank_name")]
            entity_info["component_type"] = IncidentGraphComponentType(
                entity_info.pop("component_type", IncidentGraphComponentType.PRIMARY.value)
            )
            self.incident_graph_entities[entity_info["entity_id"]] = IncidentGraphEntity(**entity_info)

        for edge_info in self.incident_snapshot_content["incident_propagation_graph"]["edges"]:
            source = self.incident_graph_entities[edge_info["source_id"]]
            target = self.incident_graph_entities[edge_info["target_id"]]
            edge_type = IncidentGraphEdgeType(edge_info["edge_type"])
            self.entity_sources[target.entity_id][edge_type].add(source.entity_id)
            self.entity_targets[source.entity_id][edge_type].add(target.entity_id)
            events = []
            for event in edge_info.get("events", []):
                events.append(
                    IncidentGraphEdgeEvent(
                        event_type=IncidentGraphEdgeEventType(event["event_type"]),
                        event_name=event["event_name"],
                        event_time=event["event_time"],
                        direction=IncidentGraphEdgeEventDirection(event["direction"]),
                        time_series=event.get("time_series", []),
                        metric_name=event.get("metric_name", ""),
                    )
                )
            self.incident_graph_edges[(source.entity_id, target.entity_id)] = IncidentGraphEdge(
                source=source,
                target=target,
                edge_type=edge_type,
                is_anomaly=edge_info.get("is_anomaly", False),
                events=events,
                anomaly_score=edge_info.get("anomaly_score", 0),
                component_type=IncidentGraphComponentType(
                    edge_info.pop("component_type", IncidentGraphComponentType.PRIMARY.value)
                ),
            )

        self.bk_biz_id = self.incident_snapshot_content["bk_biz_id"]

    def prepare_alerts(self):
        """根据故障分析结果快照构建告警所在实体的关系."""
        for alert_info in self.incident_snapshot_content["incident_alerts"]:
            incident_alert_info = copy.deepcopy(alert_info)
            entity_id = incident_alert_info.pop("entity_id")
            incident_alert_info["entity"] = self.incident_graph_entities[entity_id] if entity_id else None
            incident_alert = IncidentAlert(**incident_alert_info)
            self.alert_entity_mapping[incident_alert.id] = incident_alert

    def get_related_alert_ids(self) -> List[int]:
        """检索故障根因定位快照关联的告警详情列表.

        :return: 告警详情列表
        """
        return [int(item["id"]) for item in self.incident_snapshot_content["incident_alerts"]]

    def entity_alerts(self, entity_id) -> List[int]:
        """实体告警列表

        :param entity_id: 实体ID
        :return: 实体告警ID列表
        """
        return [
            int(item["id"])
            for item in self.incident_snapshot_content["incident_alerts"]
            if item["entity_id"] == entity_id
        ]

    def generate_entity_sub_graph(self, entity_id: str) -> "IncidentSnapshot":
        """生成资源子图

        :param entity_id: 实体ID
        :return: 资源上下游关系的资源子图
        """
        if entity_id not in self.incident_graph_entities:
            raise IncidentEntityNotFoundError({"entity_id": entity_id})
        entity = self.incident_graph_entities[entity_id]

        sub_incident_snapshot_content = copy.deepcopy(self.incident_snapshot_content)
        sub_incident_snapshot_content["incident_alerts"] = []
        sub_incident_snapshot_content["product_hierarchy_category"] = {}
        sub_incident_snapshot_content["product_hierarchy_rank"] = {}
        sub_incident_snapshot_content["incident_propagation_graph"] = {"entities": [], "edges": []}

        self.move_upstream_to_sub_graph_content(entity, "source", sub_incident_snapshot_content)
        self.move_upstream_to_sub_graph_content(entity, "target", sub_incident_snapshot_content)

        sub_incident_snapshot_content["alerts"] = len(sub_incident_snapshot_content["incident_alerts"])

        return IncidentSnapshot(sub_incident_snapshot_content)

    def generate_entity_sub_graph_from_api(
        self, incident_id: int, entity_id: str, snapshot_id: str
    ) -> "IncidentSnapshot":
        """通过图谱接口获取图谱实体的资源子图

        :param entity_id: 实体ID
        :return: 资源上下游关系的资源子图
        """
        if entity_id not in self.incident_graph_entities:
            raise IncidentEntityNotFoundError({"entity_id": entity_id})

        sub_incident_snapshot_content = api.bkdata.get_incident_topo_by_entity(
            incident_id=incident_id,
            entity_id=entity_id,
            snapshot_id=snapshot_id,
        )
        sub_incident_snapshot_content["incident_propagation_graph"] = sub_incident_snapshot_content.pop("topo", {})
        sub_incident_snapshot_content["incident_alerts"] = []
        sub_incident_snapshot_content["bk_biz_id"] = self.incident_snapshot_content["bk_biz_id"]

        for entity in sub_incident_snapshot_content["incident_propagation_graph"]["entities"]:
            entity["is_root"] = False
            entity["is_anomaly"] = False
            entity["dimensions"] = {}

            for incident_entity in self.incident_snapshot_content["incident_propagation_graph"]["entities"]:
                if incident_entity["entity_id"] == entity["entity_id"]:
                    entity["is_root"] = incident_entity["is_root"]
                    entity["is_anomaly"] = incident_entity["is_anomaly"]
                    entity["dimensions"] = incident_entity["dimensions"]

            for incident_alert in self.incident_snapshot_content["incident_alerts"]:
                if incident_alert["entity_id"] == entity["entity_id"]:
                    sub_incident_snapshot_content["incident_alerts"].append(incident_alert)

        sub_incident_snapshot_content["alerts"] = len(sub_incident_snapshot_content["incident_alerts"])

        return IncidentSnapshot(sub_incident_snapshot_content)

    def move_upstream_to_sub_graph_content(
        self, entity: IncidentGraphEntity, direct_key: str, graph_content: Dict
    ) -> None:
        """把节点关联的上游或下游加入到子图内容内容中

        :param entity: 故障实体
        :param direct_key: 上游或下游的方向key
        :param graph_content: 图内容
        """
        for edge in self.incident_graph_edges.values():
            if edge.edge_type != IncidentGraphEdgeType.DEPENDENCY:
                continue

            if direct_key == "source" and edge.target.entity_id == entity.entity_id:
                graph_content["incident_propagation_graph"]["edges"].append(edge.to_src_dict())
                self.move_upstream_to_sub_graph_content(edge.source, direct_key, graph_content)

            if direct_key == "target" and edge.source.entity_id == entity.entity_id:
                graph_content["incident_propagation_graph"]["edges"].append(edge.to_src_dict())
                self.move_upstream_to_sub_graph_content(edge.target, direct_key, graph_content)

        graph_content["incident_propagation_graph"]["entities"].append(entity.to_src_dict())
        if entity.rank.rank_name not in graph_content["product_hierarchy_rank"]:
            graph_content["product_hierarchy_rank"][entity.rank.rank_name] = entity.rank.to_src_dict()
        if entity.rank.rank_category.category_name not in graph_content["product_hierarchy_category"]:
            graph_content["product_hierarchy_category"][
                entity.rank.rank_category.category_name
            ] = entity.rank.rank_category.to_src_dict()

        for incident_alert in self.alert_entity_mapping.values():
            if incident_alert.entity.entity_id == entity.entity_id:
                graph_content["incident_alerts"].append(incident_alert.to_src_dict())

    def group_by_rank(self) -> List[Dict]:
        """根据实体ID找到所有上下游全链路，并按照rank维度分层

        :return: 按rank分层的上下游
        """
        ranks = {
            rank.rank_id: {
                **asdict(rank),
                "sub_ranks": {},
                "total": 0,
                "anomaly_count": 0,
            }
            for rank in self.incident_graph_ranks.values()
        }
        entity_type_depths = {}
        for entity in self.incident_graph_entities.values():
            if len(self.entity_sources[entity.entity_id][IncidentGraphEdgeType.DEPENDENCY]) == 0:
                entity_type_depths[entity.entity_type] = 0
                self.find_entity_type_depths(entity.entity_type, 0, entity_type_depths)

        for entity in self.incident_graph_entities.values():
            sub_rank_key = (entity.rank.rank_id, -entity_type_depths[entity.entity_type])
            if sub_rank_key not in ranks[entity.rank.rank_id]["sub_ranks"]:
                ranks[entity.rank.rank_id]["sub_ranks"][sub_rank_key] = []
            ranks[entity.rank.rank_id]["sub_ranks"][sub_rank_key].append(entity)

            if entity.is_anomaly:
                ranks[entity.rank.rank_id]["anomaly_count"] += 1
            ranks[entity.rank.rank_id]["total"] += 1

            for aggregated_entity in entity.aggregated_entities:
                if aggregated_entity.is_anomaly:
                    ranks[entity.rank.rank_id]["anomaly_count"] += 1
                ranks[entity.rank.rank_id]["total"] += 1

        final_ranks = []
        for rank_info in ranks.values():
            sorted_sub_rank_keys = sorted(rank_info["sub_ranks"].keys())
            for index, sub_rank_key in enumerate(sorted_sub_rank_keys):
                new_rank = {key: value for key, value in rank_info.items() if key != "sub_ranks"}
                new_rank["entities"] = rank_info["sub_ranks"][sub_rank_key]
                new_rank["is_sub_rank"] = True if index > 0 else False
                final_ranks.append(new_rank)

        return final_ranks

    def find_entity_type_depths(self, entity_type: str, current_depth: int, entity_type_depths: Dict) -> None:
        """递归设置每种实体在拓扑图中的深度.

        :param entity_type: 实体类型
        :param current_depth: 当前深度
        :param entity_type_depths: 实体类型深度字典
        """
        next_entity_types = set()
        for entity in self.incident_graph_entities.values():
            if entity_type == entity.entity_type:
                for target_entity_id in self.entity_targets[entity.entity_id][IncidentGraphEdgeType.DEPENDENCY]:
                    target = self.incident_graph_entities[target_entity_id]
                    if target.entity_type not in entity_type_depths:
                        next_entity_types.add(target.entity_type)
                    entity_type_depths[target.entity_type] = current_depth + 1

        for next_entity_type in list(next_entity_types):
            self.find_entity_type_depths(next_entity_type, current_depth + 1, entity_type_depths)

    def aggregate_graph(self, incident: IncidentDocument, aggregate_config: Dict = None) -> None:
        """聚合图谱

        :param aggregate_config: 聚合配置，没有则按照是否有同质化边，且被聚合节点数大于等于3进行聚合
        """
        group_by_entities = {}

        for entity_id, entity in self.incident_graph_entities.items():
            if aggregate_config is None:
                # 如果没有聚合配置，则执行自动聚合的逻辑
                key = (
                    frozenset(self.entity_sources[entity_id][IncidentGraphEdgeType.DEPENDENCY]),
                    frozenset(self.entity_targets[entity_id][IncidentGraphEdgeType.DEPENDENCY]),
                    entity.entity_type,
                    entity.logic_key(),
                    entity_id
                    if entity.is_anomaly
                    or entity.is_on_alert
                    or entity.is_root
                    or getattr(incident.feedback, "incident_root", None) == entity.entity_id
                    else "normal",
                )
            else:
                # 按照聚合配置进行聚合
                key = (
                    self.generate_aggregate_key(entity, aggregate_config),
                    entity.logic_key(),
                    entity_id
                    if entity.is_root or getattr(incident.feedback, "incident_root", None) == entity.entity_id
                    else "not_root",
                )
            if key not in group_by_entities:
                group_by_entities[key] = set()
            group_by_entities[key].add(entity.entity_id)

        for entity_ids in group_by_entities.values():
            # 聚合相同维度超过两个的图谱实体
            if len(entity_ids) >= 2:
                self.merge_entities(sorted(list(entity_ids)))

    def generate_aggregate_key(self, entity: IncidentGraphEntity, aggregate_config: Dict) -> frozenset:
        """根据聚合配置生成用于聚合的key

        :param entity: 图谱试图
        :param aggregate_config: 聚合配置
        :return: 实体ID或者聚合key的frozenset
        """
        if entity.entity_type not in aggregate_config:
            return entity.entity_id

        aggregate_bys = defaultdict(list)
        for aggregate_key in aggregate_config[entity.entity_type]["aggregate_keys"]:
            for target_entity_id in self.entity_targets[entity.entity_id][IncidentGraphEdgeType.DEPENDENCY]:
                if self.incident_graph_entities[target_entity_id].entity_type == aggregate_key:
                    aggregate_bys[aggregate_key].append(target_entity_id)
            for source_entity_id in self.entity_sources[entity.entity_id][IncidentGraphEdgeType.DEPENDENCY]:
                if self.incident_graph_entities[source_entity_id].entity_type == aggregate_key:
                    aggregate_bys[aggregate_key].append(source_entity_id)
        for aggregate_by in aggregate_bys.keys():
            aggregate_bys[aggregate_by] = frozenset(aggregate_bys[aggregate_by])

        if not aggregate_config[entity.entity_type]["aggregate_anomaly"] and (entity.is_anomaly or entity.is_on_alert):
            aggregate_bys["anomaly_key"] = entity.entity_id

        return frozenset(aggregate_bys.items())

    def merge_entities(self, entity_ids: List[str]) -> None:
        """合并同类实体

        :param entity_ids: 待合并实体列表
        """
        main_entity = self.incident_graph_entities[entity_ids[0]]
        main_entity.aggregated_entities = [self.incident_graph_entities[entity_id] for entity_id in entity_ids[1:]]
        for entity in main_entity.aggregated_entities:
            for edge_type in self.entity_targets[entity.entity_id].keys():
                for target_entity_id in self.entity_targets[entity.entity_id][edge_type]:
                    if entity.entity_id in self.entity_sources[target_entity_id][edge_type]:
                        self.entity_sources[target_entity_id][edge_type].remove(entity.entity_id)
                    self.entity_sources[target_entity_id][edge_type].add(main_entity.entity_id)

                    _from = (entity.entity_id, target_entity_id)
                    _to = (main_entity.entity_id, target_entity_id)
                    if _to not in self.incident_graph_edges:
                        self.incident_graph_edges[_to] = IncidentGraphEdge(
                            source=main_entity,
                            target=self.incident_graph_entities[target_entity_id],
                            edge_type=edge_type,
                            is_anomaly=self.incident_graph_edges[_from].is_anomaly,
                            events=self.incident_graph_edges[_from].events,
                            aggregated_edges=[self.incident_graph_edges[_from]],
                            component_type=self.incident_graph_edges[_from].component_type,
                        )
                    elif _from in self.incident_graph_edges:
                        self.incident_graph_edges[_to].is_anomaly = (
                            self.incident_graph_edges[_to].is_anomaly or self.incident_graph_edges[_from].is_anomaly
                        )
                        self.incident_graph_edges[_to].aggregated_edges.append(self.incident_graph_edges[_from])

                    del self.incident_graph_edges[(entity.entity_id, target_entity_id)]
            for edge_type in self.entity_sources[entity.entity_id].keys():
                for source_entity_id in self.entity_sources[entity.entity_id][edge_type]:
                    if entity.entity_id in self.entity_targets[source_entity_id][edge_type]:
                        self.entity_targets[source_entity_id][edge_type].remove(entity.entity_id)
                    self.entity_targets[source_entity_id][edge_type].add(main_entity.entity_id)

                    _from = (source_entity_id, entity.entity_id)
                    _to = (source_entity_id, main_entity.entity_id)
                    if _to not in self.incident_graph_edges:
                        self.incident_graph_edges[_to] = IncidentGraphEdge(
                            source=self.incident_graph_entities[source_entity_id],
                            target=main_entity,
                            edge_type=edge_type,
                            is_anomaly=self.incident_graph_edges[_from].is_anomaly,
                            events=self.incident_graph_edges[_from].events,
                            aggregated_edges=[self.incident_graph_edges[_from]],
                            component_type=self.incident_graph_edges[_from].component_type,
                        )
                    elif _from in self.incident_graph_edges:
                        self.incident_graph_edges[_to].is_anomaly = (
                            self.incident_graph_edges[_to].is_anomaly or self.incident_graph_edges[_from].is_anomaly
                        )
                        self.incident_graph_edges[_to].aggregated_edges.append(self.incident_graph_edges[_from])

                    del self.incident_graph_edges[(source_entity_id, entity.entity_id)]

            del self.entity_targets[entity.entity_id]
            del self.entity_sources[entity.entity_id]
            del self.incident_graph_entities[entity.entity_id]
