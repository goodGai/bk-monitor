/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { type PropType, type Ref, computed, defineComponent, inject, ref, watch } from 'vue';

import { Exception, Loading } from 'bkui-vue';
import { CancelToken } from 'monitor-api/index';
import { query } from 'monitor-api/modules/apm_profile';
import { typeTools } from 'monitor-common/utils';
import { type BaseDataType, type ProfilingTableItem, ViewModeType } from 'monitor-ui/chart-plugins/typings';
import { debounce } from 'throttle-debounce';

import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import { SearchType, type ToolsFormData } from '../../../pages/profiling/typings';
import ChartTitle from './chart-title/chart-title';
import FrameGraph from './flame-graph/flame-graph';
import TableGraph from './table-graph/table-graph';
import TopoGraph from './topo-graph/topo-graph';

import type { DirectionType, IQueryParams } from '../../../typings';
import type { ProfileDataUnit } from 'monitor-ui/chart-plugins/plugins/profiling-graph/utils';

import './profiling-graph.scss';

export default defineComponent({
  name: 'ProfilingGraph',
  props: {
    queryParams: {
      type: Object as PropType<IQueryParams>,
      default: () => ({
        app_name: '',
        service_name: '',
        data_type: '',
      }),
    },
  },
  setup(props) {
    // 自动刷新定时任务
    let refleshIntervalInstance = null; // 自动刷新定时任务

    /** 取消请求方法 */
    let cancelTableFlameFn = () => {};
    let cancelTopoFn = () => {};

    const toolsFormData = inject<Ref<ToolsFormData>>('toolsFormData');
    const searchType = inject<Ref<SearchType>>('profilingSearchType');

    const frameGraphRef = ref(FrameGraph);
    const empty = ref(true);
    // 当前视图模式
    const activeMode = ref<ViewModeType>(ViewModeType.Combine);
    const textDirection = ref<DirectionType>('ltr');
    const isLoading = ref(false);
    const tableData = ref<ProfilingTableItem[]>([]);
    const flameData = ref<BaseDataType>({
      name: '',
      children: undefined,
      id: '',
    });
    const unit = ref<ProfileDataUnit>('nanoseconds');
    const highlightId = ref(-1);
    const filterKeyword = ref('');
    const topoSrc = ref('');

    const flameFilterKeywords = computed(() => (filterKeyword.value?.trim?.().length ? [filterKeyword.value] : []));
    const isCompared = computed(() => (props.queryParams as IQueryParams)?.is_compared ?? false);

    watch(
      () => props.queryParams,
      debounce(16, async () => handleQuery()),
      {
        immediate: true,
        deep: true,
      }
    );
    watch(
      () => toolsFormData.value.timeRange,
      () => {
        if (searchType.value === SearchType.Profiling) {
          handleQuery();
        }
      },
      { deep: true }
    );
    watch(
      () => toolsFormData.value.refreshInterval,
      (v: number) => {
        if (refleshIntervalInstance) {
          window.clearInterval(refleshIntervalInstance);
        }
        if (v <= 0) return;
        refleshIntervalInstance = window.setInterval(() => {
          handleQuery();
        }, toolsFormData.value.refreshInterval);
      }
    );

    const getParams = (args: Record<string, any> = {}) => {
      const { queryParams } = props;
      const [start, end] = handleTransformToTimestamp(toolsFormData.value.timeRange);
      return {
        ...args,
        ...queryParams,
        ...(searchType.value === SearchType.Profiling
          ? {
              start: start * Math.pow(10, 6),
              end: end * Math.pow(10, 6),
            }
          : {}),
      };
    };
    const handleQuery = async () => {
      getTableFlameData();
      if (isCompared.value) {
        // 对比模式下不展示拓扑图
        if (activeMode.value === ViewModeType.Topo) {
          activeMode.value = ViewModeType.Combine;
        }
      } else {
        getTopoSrc();
      }
    };
    /** 获取表格和火焰图 */
    const getTableFlameData = async () => {
      isLoading.value = true;
      highlightId.value = -1;
      cancelTableFlameFn();

      const params = getParams({ diagram_types: ['table', 'flamegraph'] });
      await query(params, {
        cancelToken: new CancelToken((c: () => void) => (cancelTableFlameFn = c)),
      })
        .then(data => {
          if (data && Object.keys(data)?.length) {
            unit.value = data.unit || '';
            tableData.value = data.table_data?.items ?? [];
            flameData.value = data.flame_data;
            empty.value = false;
          } else {
            empty.value = true;
          }
          isLoading.value = false;
        })
        .catch(e => {
          if (e.message) {
            isLoading.value = false;
          }
        });
    };
    /** 获取拓扑图 */
    const getTopoSrc = async () => {
      cancelTopoFn();

      if (ViewModeType.Topo === activeMode.value) {
        isLoading.value = true;
      }

      const params = getParams({ diagram_types: ['callgraph'] });
      await query(params, {
        cancelToken: new CancelToken((c: () => void) => (cancelTopoFn = c)),
      })
        .then(data => {
          if (data) {
            topoSrc.value = data.call_graph_data || '';
          }
          isLoading.value = false;
        })
        .catch(e => {
          if (e.message) {
            isLoading.value = false;
          }
        });
    };
    /** 切换视图模式 */
    const handleModeChange = async (val: ViewModeType) => {
      if (val === activeMode.value) return;

      highlightId.value = -1;
      activeMode.value = val;
    };
    const handleTextDirectionChange = (val: DirectionType) => {
      textDirection.value = val;
    };
    /** 表格排序 */
    const handleSortChange = () => {
      // const params = getParams({
      //   diagram_types: ['table'],
      //   sort: sortKey
      // });
      // const data = await query(params).catch(() => false);
      // if (data) {
      //   highlightId.value = -1;
      //   tableData.value = data.table_data?.items ?? [];
      // }
      highlightId.value = -1;
    };
    /** 下载 */
    const handleDownload = async (type: string) => {
      switch (type) {
        case 'png':
          frameGraphRef.value?.handleStoreImg();
          break;
        case 'pprof': {
          const params = getParams({ export_format: 'pprof' });
          const downloadUrl = `/apm/profile_api/query/export/?bk_biz_id=${window.bk_biz_id}${getUrlParamsString(
            params
          )}`;
          const a = document.createElement('a');
          a.style.display = 'none';
          a.href = downloadUrl;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          break;
        }
        default:
          break;
      }
    };

    function getUrlParamsString(obj) {
      const str = Object.keys(obj)
        .reduce((ary, key) => {
          if (obj[key]) {
            ary.push(
              `${encodeURIComponent(key)}=${encodeURIComponent(
                typeTools.isObject(obj[key]) ? JSON.stringify(obj[key]) : obj[key]
              )}`
            );
          }
          return ary;
        }, [])
        .join('&');
      if (str.length) return `&${str}`;
      return '';
    }

    return {
      frameGraphRef,
      empty,
      tableData,
      flameData,
      unit,
      isLoading,
      activeMode,
      textDirection,
      handleModeChange,
      handleTextDirectionChange,
      highlightId,
      filterKeyword,
      flameFilterKeywords,
      handleSortChange,
      handleDownload,
      topoSrc,
      isCompared,
    };
  },
  render() {
    return (
      <Loading
        class='profiling-graph'
        loading={this.isLoading}
      >
        <ChartTitle
          activeMode={this.activeMode}
          isCompared={this.isCompared}
          textDirection={this.textDirection}
          onDownload={this.handleDownload}
          onKeywordChange={val => (this.filterKeyword = val)}
          onModeChange={this.handleModeChange}
          onTextDirectionChange={this.handleTextDirectionChange}
        />
        {this.empty ? (
          <Exception
            description={this.$t('暂无数据')}
            type='empty'
          />
        ) : (
          <div class='profiling-graph-content'>
            {[ViewModeType.Combine, ViewModeType.Table].includes(this.activeMode) && (
              <TableGraph
                data={this.tableData}
                dataType={this.queryParams.data_type}
                filterKeyword={this.filterKeyword}
                highlightId={this.highlightId}
                isCompared={this.isCompared}
                textDirection={this.textDirection}
                unit={this.unit}
                onSortChange={this.handleSortChange}
                onUpdateHighlightId={id => (this.highlightId = id)}
              />
            )}
            {[ViewModeType.Combine, ViewModeType.Flame].includes(this.activeMode) && (
              <FrameGraph
                ref='frameGraphRef'
                appName={this.$props.queryParams.app_name}
                data={this.flameData}
                filterKeywords={this.flameFilterKeywords}
                highlightId={this.highlightId}
                isCompared={this.isCompared}
                showGraphTools={false}
                textDirection={this.textDirection}
                unit={this.unit}
                onUpdateHighlightId={id => (this.highlightId = id)}
              />
            )}
            {ViewModeType.Topo === this.activeMode && <TopoGraph topoSrc={this.topoSrc} />}
          </div>
        )}
      </Loading>
    );
  },
});
