<template>
  <section class="page-stack workflow-v2-page">
    <div class="toolbar">
      <div class="toolbar-left">
        <strong>订单进度</strong>
        <el-tag v-if="graph" :type="graph.status === 'completed' ? 'success' : 'warning'">
          {{ workflowStatusLabel(graph.status) }}
        </el-tag>
      </div>
      <div class="toolbar-left">
        <el-button :icon="Refresh" :loading="loading" @click="reloadAll">刷新</el-button>
      </div>
    </div>

    <div class="metric-grid workflow-metrics">
      <el-card v-for="metric in metrics" :key="metric.label" shadow="never" class="metric-card">
        <span>{{ metric.label }}</span>
        <strong>{{ metric.value }}</strong>
        <small>{{ metric.note }}</small>
      </el-card>
    </div>

    <div class="workflow-layout">
      <div class="workflow-sidebar">
        <el-card v-if="canUsePreOrders" shadow="never" class="table-card pre-order-panel">
          <template #header>
            <div class="panel-title">
              <span>预订单</span>
              <div class="panel-actions">
                <el-tag>{{ preOrders.length }} 条</el-tag>
                <el-button v-if="canCreatePreOrder" size="small" type="primary" :icon="Plus" @click="openPreOrderDialog">
                  新增
                </el-button>
              </div>
            </div>
          </template>

          <div class="pre-order-filters">
            <el-input
              v-model="preOrderKeyword"
              clearable
              :prefix-icon="Search"
              placeholder="预订单 / 客户 / 产品"
              @keyup.enter="loadPreOrders"
            />
            <el-select v-model="preOrderStatusFilter" clearable placeholder="状态" @change="loadPreOrders">
              <el-option label="已提交" value="submitted" />
              <el-option label="客户已确认" value="customer_approved" />
              <el-option label="客户驳回" value="customer_rejected" />
              <el-option label="已转订单" value="converted" />
            </el-select>
            <el-button :icon="Refresh" @click="loadPreOrders" />
          </div>

          <el-table
            v-loading="preOrdersLoading"
            :data="preOrders"
            stripe
            height="300"
            empty-text="暂无预订单"
            class="pre-order-table"
          >
            <el-table-column prop="pre_order_no" label="预订单号" width="132" show-overflow-tooltip />
            <el-table-column label="客户 / 产品" min-width="170" show-overflow-tooltip>
              <template #default="{ row }">
                <div class="stacked-cell">
                  <strong>{{ row.customer_name }}</strong>
                  <span>{{ row.product_name }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="num" label="套数" width="72" />
            <el-table-column prop="status" label="状态" width="112">
              <template #default="{ row }">
                <el-tag size="small" :type="preOrderStatusType(row.status)">{{ preOrderStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="190" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="canConfirmPreOrder"
                  text
                  type="success"
                  :disabled="!canApprovePreOrder(row)"
                  @click.stop="approvePreOrder(row)"
                >
                  批准
                </el-button>
                <el-button
                  v-if="canConfirmPreOrder"
                  text
                  type="danger"
                  :disabled="!canRejectPreOrder(row)"
                  @click.stop="rejectPreOrder(row)"
                >
                  驳回
                </el-button>
                <el-button
                  v-if="canConvertPreOrder"
                  text
                  type="primary"
                  :disabled="row.status !== 'customer_approved'"
                  @click.stop="openConvertDialog(row)"
                >
                  转订单
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card shadow="never" class="table-card workflow-order-panel">
        <template #header>
          <div class="panel-title">
            <span>{{ canBrowseOrders ? '订单选择' : '我的任务' }}</span>
            <el-tag>{{ canBrowseOrders ? orders.length : myTasks.length }} 条</el-tag>
          </div>
        </template>

        <div class="account-scope">
          <el-tag>{{ session.user?.real_name || session.user?.username }}</el-tag>
          <el-tag v-if="session.user?.department" type="info">{{ session.user.department }}</el-tag>
          <el-tag :type="canBrowseOrders ? 'success' : 'warning'">
            {{ canBrowseOrders ? '全部订单视图' : '我的待办视图' }}
          </el-tag>
        </div>

        <template v-if="canBrowseOrders">
        <div class="workflow-order-filters">
          <el-input
            v-model="keyword"
            clearable
            :prefix-icon="Search"
            placeholder="订单 / 客户 / 产品"
            @keyup.enter="loadOrders"
          />
          <el-select v-model="statusFilter" clearable placeholder="状态" @change="loadOrders">
            <el-option label="已确认" value="confirmed" />
            <el-option label="生产中" value="in_production" />
            <el-option label="待送货" value="pending_delivery" />
            <el-option label="已签收/已送货" value="delivered" />
            <el-option label="已归档" value="archived" />
          </el-select>
          <el-button :icon="Refresh" @click="loadOrders" />
        </div>

        <el-table
          :data="orders"
          stripe
          height="520"
          highlight-current-row
          class="workflow-order-table"
          @row-click="selectOrder"
          @row-dblclick="selectOrder"
        >
          <el-table-column prop="order_no" label="订单号" min-width="150" show-overflow-tooltip />
          <el-table-column prop="product_summary" label="产品" min-width="150" show-overflow-tooltip />
          <el-table-column prop="status" label="状态" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="orderStatusType(row.status)">{{ orderStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
        </template>

        <template v-else>
          <el-table
            :data="myTasks"
            stripe
            height="520"
            highlight-current-row
            empty-text="当前账号暂无待处理工作"
            class="workflow-order-table"
            @row-click="selectTask"
            @row-dblclick="selectTask"
          >
            <el-table-column prop="node_name" label="工作项" min-width="150" show-overflow-tooltip />
            <el-table-column prop="department" label="部门" width="110" />
            <el-table-column prop="status" label="状态" width="110">
              <template #default="{ row }">
                <el-tag size="small" :type="nodeTagType(row.status)">{{ nodeStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="waiting_reason" label="等待" min-width="150" show-overflow-tooltip />
          </el-table>
        </template>
        </el-card>
      </div>

      <div class="workflow-main">
        <el-card shadow="never" class="panel-card workflow-action-card">
          <template #header>
            <div class="panel-title">
              <span>当前订单</span>
              <el-tag v-if="selectedOrder">{{ selectedOrder.order_no }}</el-tag>
            </div>
          </template>

          <div v-if="selectedSalesOrderId" class="selected-order">
            <div>
              <span class="muted-label">产品</span>
              <strong>{{ selectedOrder?.product_summary || '部门任务订单' }}</strong>
            </div>
            <div>
              <span class="muted-label">交期</span>
              <strong>{{ selectedOrder?.due_date || '-' }}</strong>
            </div>
            <div>
              <span class="muted-label">订单状态</span>
              <strong>{{ selectedOrder ? orderStatusLabel(selectedOrder.status) : workflowStatusLabel(graph?.status) }}</strong>
            </div>
            <div class="workflow-actions">
              <el-button
                v-if="selectedOrder"
                type="primary"
                :icon="VideoPlay"
                :loading="starting"
                :disabled="Boolean(graph) || !canStartWorkflow"
                @click="startWorkflow"
              >
                开始跟进生产
              </el-button>
              <el-button v-if="selectedOrder" :icon="View" @click="goOrderDetail">订单详情</el-button>
            </div>
          </div>
          <el-empty v-else description="请选择一张订单" />
        </el-card>

        <el-card v-if="graph" shadow="never" class="panel-card next-action-card">
          <template #header>
            <div class="panel-title">
              <span>现在要处理</span>
              <el-tag :type="activeNodes.length ? 'warning' : 'success'">{{ activeNodes.length || '无' }}</el-tag>
            </div>
          </template>

          <div v-if="activeNodes.length" class="next-action-list">
            <div
              v-for="node in activeNodes"
              :key="node.id"
              class="next-action-item"
              :class="[`node-${node.status}`]"
            >
              <div class="next-action-main">
                <el-tag size="small" :type="nodeTagType(node.status)">{{ nodeStatusLabel(node.status) }}</el-tag>
                <div>
                  <strong>{{ node.node_name }}</strong>
                  <span>{{ node.department || '相关部门' }}</span>
                </div>
              </div>
              <div class="next-action-note">
                {{ currentActionText(node) }}
              </div>
              <div class="next-action-buttons">
                <el-button
                  v-if="node.status === 'active'"
                  size="small"
                  :icon="VideoPlay"
                  :loading="operatingNodeId === node.id"
                  :disabled="!canOperateNode(node)"
                  @click="startNode(node)"
                >
                  开始
                </el-button>
                <el-button
                  size="small"
                  type="success"
                  :icon="CircleCheck"
                  :loading="operatingNodeId === node.id"
                  :disabled="!canOperateNode(node)"
                  @click="handleCompleteNode(node)"
                >
                  {{ nodeCompleteActionText(node) }}
                </el-button>
              </div>
            </div>
          </div>
          <el-empty v-else description="当前没有待处理工作" />
        </el-card>

        <el-card v-if="selectedSalesOrderId" shadow="never" class="panel-card fulfillment-card">
          <template #header>
            <div class="panel-title">
              <span>财务 / 送货 / 签收</span>
              <el-tag :type="fulfillmentStageType">{{ fulfillmentStageLabel(fulfillmentSummary?.current_stage) }}</el-tag>
            </div>
          </template>

          <div class="fulfillment-grid">
            <div class="fulfillment-step" :class="{ done: Boolean(fulfillmentSummary?.bill?.released_at), active: fulfillmentSummary?.current_stage === 'billing' || fulfillmentSummary?.current_stage === 'released' }">
              <span>Bill</span>
              <strong>{{ fulfillmentSummary?.bill?.bill_no || (fulfillmentSummary?.current_stage === 'production' ? '生产中' : '等待财务处理') }}</strong>
              <small>{{ fulfillmentSummary?.bill ? billStatusLabel(fulfillmentSummary.bill.bill_status) : (fulfillmentSummary?.current_stage === 'production' ? '生产完成后生成' : '检验通过后生成') }}</small>
              <small v-if="fulfillmentSummary?.can_view_amount && fulfillmentSummary.bill?.amount !== undefined">
                金额 {{ formatAmount(fulfillmentSummary.bill.amount) }}
              </small>
            </div>
            <div class="fulfillment-step" :class="{ done: ['shipped', 'signed'].includes(fulfillmentSummary?.delivery?.status || ''), active: fulfillmentSummary?.current_stage === 'shipped' }">
              <span>送货</span>
              <strong>{{ fulfillmentSummary?.delivery?.delivery_no || '等待送货单' }}</strong>
              <small>{{ fulfillmentSummary?.delivery ? deliveryStatusLabel(fulfillmentSummary.delivery.status) : '财务放行后送货' }}</small>
              <small v-if="fulfillmentSummary?.delivery?.delivery_time">{{ fulfillmentSummary.delivery.delivery_time }}</small>
            </div>
            <div class="fulfillment-step" :class="{ done: Boolean(fulfillmentSummary?.sign), active: fulfillmentSummary?.current_stage === 'signed' }">
              <span>签收</span>
              <strong>{{ fulfillmentSummary?.sign?.signed_by || fulfillmentSummary?.delivery?.signed_by || '等待客户签收' }}</strong>
              <small>{{ fulfillmentSummary?.sign?.signed_at || fulfillmentSummary?.delivery?.signed_at || '送货完成后登记' }}</small>
              <small v-if="fulfillmentSummary?.sign?.remarks">{{ fulfillmentSummary.sign.remarks }}</small>
            </div>
          </div>
        </el-card>

        <el-card v-if="selectedSalesOrderId" shadow="never" class="panel-card abnormal-card">
          <template #header>
            <div class="panel-title">
              <span>异常处理</span>
              <div class="panel-actions">
                <el-tag>{{ abnormalFlows.length }} 条</el-tag>
                <el-button
                  v-if="canCreateAbnormalFlow"
                  size="small"
                  type="warning"
                  :icon="Warning"
                  :disabled="!selectedSalesOrderId || !graph"
                  @click="openAbnormalDialog"
                >
                  新建异常
                </el-button>
              </div>
            </div>
          </template>

          <el-table :data="abnormalFlows" stripe size="small" empty-text="暂无异常记录">
            <el-table-column prop="abnormal_type" label="类型" width="110">
              <template #default="{ row }">
                <el-tag size="small" type="warning">{{ abnormalTypeLabel(row.abnormal_type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="从哪一步开始" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ workflowNodeLabel(row.selected_start_node) }}</template>
            </el-table-column>
            <el-table-column label="需要重做" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">{{ abnormalProcessText(row.selected_process_nodes) }}</template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="120">
              <template #default="{ row }">
                <el-tag size="small" :type="abnormalStatusType(row.status)">{{ abnormalStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="reason" label="原因" min-width="180" show-overflow-tooltip />
            <el-table-column v-if="canApproveAbnormalFlow" label="操作" width="210" fixed="right">
              <template #default="{ row }">
                <el-button
                  text
                  type="warning"
                  :loading="operatingAbnormalFlowId === row.id"
                  :disabled="row.status !== 'pending_approval'"
                  @click.stop="approveAbnormalFlow(row)"
                >
                  批准返工
                </el-button>
                <el-button
                  text
                  type="danger"
                  :loading="operatingAbnormalFlowId === row.id"
                  :disabled="row.status !== 'pending_approval'"
                  @click.stop="rejectAbnormalFlow(row)"
                >
                  驳回
                </el-button>
                <el-button
                  text
                  type="success"
                  :loading="operatingAbnormalFlowId === row.id"
                  :disabled="row.status !== 'processing'"
                  @click.stop="completeAbnormalFlow(row)"
                >
                  完成
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card shadow="never" class="panel-card join-card">
          <template #header>
            <div class="panel-title">
              <span>生产放行检查</span>
              <el-tag :type="joinCheck?.ready ? 'success' : 'warning'">{{ joinLabel }}</el-tag>
            </div>
          </template>
          <div class="join-grid">
            <div :class="{ done: joinCheck?.epin_completed }">
              <CircleCheck class="join-icon" />
              <span>电拼完成</span>
              <strong>{{ joinCheck?.epin_completed ? '已完成' : '等待' }}</strong>
            </div>
            <div :class="{ done: joinCheck?.copper_grind_completed }">
              <CircleCheck class="join-icon" />
              <span>铜磨 / 研磨完成</span>
              <strong>{{ joinCheck?.copper_grind_completed ? '已完成' : '等待' }}</strong>
            </div>
            <div class="join-reason">
              <Warning class="join-icon" />
              <span>等待项</span>
              <strong>{{ joinWaitingText }}</strong>
            </div>
          </div>
        </el-card>

        <div v-if="graph" class="making-epin-grid">
          <el-card v-if="canSeeMakingPanel" shadow="never" class="panel-card">
            <template #header>
              <div class="panel-title">
                <span>制作主管派工</span>
                <el-tag>{{ assignedSets }} / {{ orderQuantity }}</el-tag>
              </div>
            </template>

            <div v-if="canAssignMaking" class="assignment-editor">
              <div
                v-for="(draft, index) in assignmentDrafts"
                :key="index"
                class="assignment-draft"
              >
                <el-select v-model="draft.employee_id" filterable placeholder="制作员工">
                  <el-option
                    v-for="user in productionUsers"
                    :key="user.id"
                    :label="userLabel(user.id)"
                    :value="user.id"
                  />
                </el-select>
                <el-input-number v-model="draft.assigned_sets" :min="1" :precision="0" class="assignment-number" />
                <el-input v-model="draft.remarks" clearable placeholder="备注" />
                <el-button text type="danger" :disabled="assignmentDrafts.length === 1" @click="removeAssignmentDraft(index)">
                  删除
                </el-button>
              </div>
              <div class="assignment-actions">
                <el-button :icon="Plus" @click="addAssignmentDraft">追加员工</el-button>
                <el-button
                  type="primary"
                  :loading="assigning"
                  :disabled="!selectedOrder || !canAssignMaking"
                  @click="submitAssignments"
                >
                  保存派工
                </el-button>
              </div>
            </div>

            <el-table :data="makingAssignments" stripe size="small" empty-text="暂无制作派工">
              <el-table-column label="员工" min-width="120">
                <template #default="{ row }">{{ userLabel(row.employee_id) }}</template>
              </el-table-column>
              <el-table-column prop="assigned_sets" label="分配" width="82" />
              <el-table-column prop="completed_sets" label="完成" width="82" />
              <el-table-column prop="status" label="状态" width="110">
                <template #default="{ row }">
                  <el-tag size="small">{{ makingStatusLabel(row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="本次完成" width="140">
                <template #default="{ row }">
                  <el-input-number
                    v-model="completionByAssignment[row.id]"
                    :min="1"
                    :max="Math.max(1, row.assigned_sets - row.completed_sets)"
                    :precision="0"
                    size="small"
                    class="inline-number"
                  />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="150" fixed="right">
                <template #default="{ row }">
                  <el-button text type="primary" @click="completeAssignment(row)">完成</el-button>
                  <el-button text type="success" :disabled="Boolean(row.submitted_to_epin_at)" @click="submitAssignmentToEpin(row)">
                    电拼
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <el-card v-if="canSeeEpinPanel" shadow="never" class="panel-card">
            <template #header>
              <div class="panel-title">
                <span>电拼批次</span>
                <el-tag type="info">{{ epinBatches.length }}</el-tag>
              </div>
            </template>
            <el-table :data="epinBatches" stripe size="small" empty-text="暂无电拼批次">
              <el-table-column label="来源员工" min-width="120">
                <template #default="{ row }">{{ userLabel(row.employee_id) }}</template>
              </el-table-column>
              <el-table-column prop="sets_count" label="套数" width="82" />
              <el-table-column prop="status" label="状态" width="110">
                <template #default="{ row }">
                  <el-tag size="small" :type="row.status === 'completed' ? 'success' : 'warning'">
                    {{ epinStatusLabel(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="received_at" label="接收时间" min-width="150" show-overflow-tooltip />
              <el-table-column prop="completed_at" label="完成时间" min-width="150" show-overflow-tooltip />
              <el-table-column label="操作" width="130" fixed="right">
                <template #default="{ row }">
                  <el-button text type="primary" :disabled="row.status !== 'submitted'" @click="receiveEpin(row)">接收</el-button>
                  <el-button text type="success" :disabled="row.status === 'completed'" @click="completeEpin(row)">完成</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </div>

        <el-card v-if="graph" shadow="never" class="panel-card workflow-graph-card">
          <template #header>
            <div class="panel-title">
              <span>订单进度</span>
              <el-tag>按部门推进</el-tag>
            </div>
          </template>

          <div class="workflow-sections">
            <div v-for="section in flowSections" :key="section.key" class="workflow-section">
              <div class="workflow-section-title">
                <strong>{{ section.title }}</strong>
                <el-tag size="small" type="info">{{ section.nodes.length }}</el-tag>
              </div>
              <div class="workflow-node-row" :class="{ empty: section.nodes.length === 0 }">
                <template v-if="section.nodes.length">
                  <div
                    v-for="node in section.nodes"
                    :key="node.node_code"
                    class="workflow-node"
                    :class="[`node-${node.status}`, { current: node.is_current }]"
                  >
                    <div class="node-head">
                      <el-tag size="small" :type="nodeTagType(node.status)">{{ nodeStatusLabel(node.status) }}</el-tag>
                      <span>{{ node.department || '-' }}</span>
                    </div>
                    <strong>{{ node.node_name }}</strong>
                    <small>{{ nodeHelpText(node) }}</small>
                    <div v-if="graph && node.is_current" class="node-actions">
                      <el-button
                        v-if="node.status === 'active'"
                        size="small"
                        :icon="VideoPlay"
                        :loading="operatingNodeId === node.id"
                        :disabled="!canOperateNode(node)"
                        title="开始这一步"
                        aria-label="开始这一步"
                        @click="startNode(node)"
                      />
                      <el-button
                        size="small"
                        type="success"
                        :icon="CircleCheck"
                        :loading="operatingNodeId === node.id"
                        :disabled="!canOperateNode(node)"
                        :title="nodeCompleteActionText(node)"
                        :aria-label="nodeCompleteActionText(node)"
                        @click="handleCompleteNode(node)"
                      />
                    </div>
                  </div>
                </template>
                <el-empty v-else description="暂无工作项" />
              </div>
            </div>
          </div>
        </el-card>

      </div>
    </div>

    <el-dialog v-model="preOrderDialogVisible" title="新增预订单" width="640px" destroy-on-close>
      <el-form label-position="top" class="pre-order-form">
        <el-form-item label="关联客户">
          <el-select
            v-model="preOrderForm.customer_id"
            filterable
            clearable
            placeholder="客户"
            @visible-change="handleCustomerDropdown"
            @change="syncPreOrderCustomerName"
          >
            <el-option
              v-for="customer in customers"
              :key="customer.id"
              :label="customerLabel(customer)"
              :value="customer.id"
            />
          </el-select>
        </el-form-item>
        <div class="form-grid two-columns">
          <el-form-item label="样稿号" required>
            <el-input v-model="preOrderForm.sample_no" clearable />
          </el-form-item>
          <el-form-item label="客户名称" required>
            <el-input v-model="preOrderForm.customer_name" clearable />
          </el-form-item>
          <el-form-item label="产品名称" required>
            <el-input v-model="preOrderForm.product_name" clearable />
          </el-form-item>
          <el-form-item label="类型">
            <el-input v-model="preOrderForm.type" clearable />
          </el-form-item>
          <el-form-item label="套数" required>
            <el-input-number v-model="preOrderForm.num" :min="1" :precision="0" class="full-width" />
          </el-form-item>
          <el-form-item label="印色">
            <el-input v-model="preOrderForm.print_color" clearable />
          </el-form-item>
        </div>
        <el-form-item label="备注">
          <el-input v-model="preOrderForm.remarks" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="preOrderDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creatingPreOrder" @click="submitPreOrder">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="convertDialogVisible" title="转销售订单" width="560px" destroy-on-close>
      <el-form label-position="top" class="pre-order-form">
        <el-form-item label="客户" required>
          <el-select
            v-model="convertForm.customer_id"
            filterable
            placeholder="客户"
            @visible-change="handleCustomerDropdown"
          >
            <el-option
              v-for="customer in customers"
              :key="customer.id"
              :label="customerLabel(customer)"
              :value="customer.id"
            />
          </el-select>
        </el-form-item>
        <div class="form-grid two-columns">
          <el-form-item label="交期" required>
            <el-date-picker
              v-model="convertForm.due_date"
              type="date"
              value-format="YYYY-MM-DD"
              class="full-width"
            />
          </el-form-item>
          <el-form-item label="优先级">
            <el-select v-model="convertForm.priority">
              <el-option label="普通" value="normal" />
              <el-option label="加急" value="urgent" />
              <el-option label="低" value="low" />
            </el-select>
          </el-form-item>
          <el-form-item label="单价">
            <el-input-number v-model="convertForm.unit_price" :min="0" :precision="2" class="full-width" />
          </el-form-item>
          <el-form-item label="预订单">
            <el-input :model-value="selectedPreOrder?.pre_order_no || '-'" disabled />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="convertDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="convertingPreOrder" @click="submitConvertPreOrder">转为订单</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="abnormalDialogVisible" title="新建异常处理" width="680px" destroy-on-close>
      <el-form label-position="top" class="pre-order-form">
        <div class="form-grid two-columns">
          <el-form-item label="异常类型" required>
            <el-select v-model="abnormalForm.abnormal_type" placeholder="异常类型">
              <el-option label="质量返工" value="quality_rework" />
              <el-option label="客户变更" value="customer_change" />
              <el-option label="生产异常" value="production_exception" />
              <el-option label="补做" value="supplement" />
            </el-select>
          </el-form-item>
          <el-form-item label="从哪一步开始" required>
            <el-select v-model="abnormalForm.selected_start_node" filterable placeholder="从哪一步开始">
              <el-option
                v-for="node in abnormalStartNodeOptions"
                :key="node.node_code"
                :label="workflowNodeLabel(node.node_code)"
                :value="node.node_code"
              />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="需要重做" required>
          <el-select
            v-model="abnormalForm.selected_process_nodes"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="需要重做"
          >
            <el-option
              v-for="node in abnormalProcessNodeOptions"
              :key="node.node_code"
              :label="workflowNodeLabel(node.node_code)"
              :value="node.node_code"
            />
          </el-select>
        </el-form-item>
        <div class="abnormal-switches">
          <el-checkbox v-model="abnormalForm.need_inspection">需要检验</el-checkbox>
          <el-checkbox v-model="abnormalForm.need_finance_bill">需要财务开票</el-checkbox>
          <el-checkbox v-model="abnormalForm.need_delivery">需要送货</el-checkbox>
        </div>
        <el-form-item label="原因" required>
          <el-input v-model="abnormalForm.reason" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="abnormalDialogVisible = false">取消</el-button>
        <el-button type="warning" :loading="creatingAbnormalFlow" @click="submitAbnormalFlow">提交异常</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="nodeActionDialogVisible"
      :title="nodeActionDialogTitle"
      width="620px"
      destroy-on-close
    >
      <el-form label-position="top" class="pre-order-form">
        <template v-if="activeActionNode?.node_code === 'finance_bill'">
          <div class="form-grid two-columns">
            <el-form-item label="Bill 编号" required>
              <el-input v-model="nodeActionForm.bill_no" clearable />
            </el-form-item>
            <el-form-item label="送货单号" required>
              <el-input v-model="nodeActionForm.delivery_note_no" clearable />
            </el-form-item>
            <el-form-item label="Bill 金额">
              <el-input-number v-model="nodeActionForm.bill_amount" :min="0" :precision="2" class="full-width" />
            </el-form-item>
            <el-form-item label="放行人">
              <el-input :model-value="currentUserName" disabled />
            </el-form-item>
          </div>
          <el-form-item label="放行说明">
            <el-input v-model="nodeActionForm.remarks" type="textarea" :rows="3" />
          </el-form-item>
        </template>

        <template v-else-if="activeActionNode?.node_code === 'delivery'">
          <div class="form-grid two-columns">
            <el-form-item label="送货时间" required>
              <el-date-picker
                v-model="nodeActionForm.delivery_time"
                type="datetime"
                value-format="YYYY-MM-DD HH:mm:ss"
                class="full-width"
              />
            </el-form-item>
            <el-form-item label="送货人 / 司机" required>
              <el-input v-model="nodeActionForm.delivery_person" clearable />
            </el-form-item>
            <el-form-item label="物流 / 车号">
              <el-input v-model="nodeActionForm.logistics" clearable />
            </el-form-item>
            <el-form-item label="客户地址">
              <el-input v-model="nodeActionForm.delivery_address" clearable />
            </el-form-item>
          </div>
          <el-form-item label="送货备注">
            <el-input v-model="nodeActionForm.remarks" type="textarea" :rows="3" />
          </el-form-item>
        </template>

        <template v-else-if="activeActionNode?.node_code === 'sign'">
          <div class="form-grid two-columns">
            <el-form-item label="签收人" required>
              <el-input v-model="nodeActionForm.signer" clearable />
            </el-form-item>
            <el-form-item label="签收时间" required>
              <el-date-picker
                v-model="nodeActionForm.signed_at"
                type="datetime"
                value-format="YYYY-MM-DD HH:mm:ss"
                class="full-width"
              />
            </el-form-item>
            <el-form-item label="签收单号 / 凭证">
              <el-input v-model="nodeActionForm.sign_proof_no" clearable />
            </el-form-item>
            <el-form-item label="登记人">
              <el-input :model-value="currentUserName" disabled />
            </el-form-item>
          </div>
          <el-form-item label="签收备注">
            <el-input v-model="nodeActionForm.remarks" type="textarea" :rows="3" />
          </el-form-item>
        </template>

        <template v-else>
          <el-form-item label="完成备注">
            <el-input v-model="nodeActionForm.remarks" type="textarea" :rows="4" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="nodeActionDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="nodeActionSubmitting" @click="submitNodeAction">
          {{ nodeActionConfirmText }}
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { CircleCheck, Plus, Refresh, Search, VideoPlay, View, Warning } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type {
  AbnormalFlow,
  AbnormalFlowCreatePayload,
  ConvertPreOrderPayload,
  Customer,
  EpinBatch,
  MakingAssignment,
  PageResponse,
  PreOrder,
  PreOrderCreatePayload,
  SalesOrder,
  UserOption,
  WorkflowGraph,
  WorkflowFulfillmentSummary,
  WorkflowJoinCheck,
  WorkflowNode
} from '../api/types'
import { hasPermission, session } from '../stores/session'
import { sortCustomersForCurrentUser } from '../utils/customerPriority'
import { orderStatusMap, statusLabel } from '../utils/status'

interface DisplayNode {
  node_code: string
  node_name: string
  department?: string
  node_type: string
  branch_code?: string
  sort_order: number
  status: string
  is_current: boolean
  waiting_reason?: string
  id?: string
  assigned_user_id?: string
}

interface NodeActionForm {
  bill_no: string
  delivery_note_no: string
  bill_amount: number
  delivery_time: string
  delivery_person: string
  logistics: string
  delivery_address: string
  signer: string
  signed_at: string
  sign_proof_no: string
  remarks: string
}

const router = useRouter()
const loading = ref(false)
const starting = ref(false)
const assigning = ref(false)
const operatingNodeId = ref<string | null>(null)
const graph = ref<WorkflowGraph | null>(null)
const joinCheck = ref<WorkflowJoinCheck | null>(null)
const fulfillmentSummary = ref<WorkflowFulfillmentSummary | null>(null)
const orders = ref<SalesOrder[]>([])
const selectedOrder = ref<SalesOrder | null>(null)
const selectedSalesOrderId = ref<string | null>(null)
const myTasks = ref<WorkflowNode[]>([])
const users = ref<UserOption[]>([])
const makingAssignments = ref<MakingAssignment[]>([])
const epinBatches = ref<EpinBatch[]>([])
const customers = ref<Customer[]>([])
const preOrders = ref<PreOrder[]>([])
const abnormalFlows = ref<AbnormalFlow[]>([])
const keyword = ref('')
const statusFilter = ref('')
const preOrderKeyword = ref('')
const preOrderStatusFilter = ref('')
const preOrdersLoading = ref(false)
const preOrderDialogVisible = ref(false)
const creatingPreOrder = ref(false)
const convertDialogVisible = ref(false)
const convertingPreOrder = ref(false)
const selectedPreOrder = ref<PreOrder | null>(null)
const preOrderForm = ref<PreOrderCreatePayload>(blankPreOrderForm())
const convertForm = ref<ConvertPreOrderPayload>(blankConvertForm())
const abnormalDialogVisible = ref(false)
const creatingAbnormalFlow = ref(false)
const abnormalForm = ref<AbnormalFlowCreatePayload>(blankAbnormalForm())
const operatingAbnormalFlowId = ref<string | null>(null)
const nodeActionDialogVisible = ref(false)
const nodeActionSubmitting = ref(false)
const activeActionNode = ref<WorkflowNode | DisplayNode | null>(null)
const nodeActionForm = ref<NodeActionForm>(blankNodeActionForm())
const assignmentDrafts = ref([{ employee_id: '', assigned_sets: 1, remarks: '' }])
const completionByAssignment = ref<Record<string, number>>({})
const forbiddenAbnormalProcessNodes = new Set(['delivery', 'sign', 'completed'])
const historicalOrderStatuses = new Set(['paid', 'archived', 'cancelled'])
const departmentKeywords: Record<string, string[]> = {
  制作: ['制作', '看样制作', 'production'],
  电拼: ['电拼', 'carving make-up', 'make-up', 'makeup'],
  卷板: ['卷板', 'sheet bending'],
  法版: ['法版', '法兰', 'flange'],
  车床: ['车床', 'lathe', '机加工'],
  磨床: ['磨床', '基磨', 'basic grinding', '机加工'],
  镀铜: ['镀铜', '镀铬', '退铬', 'plating', 'chrome'],
  研磨: ['研磨', '铜磨', 'copper grinding'],
  雕刻: ['雕刻', '电雕', 'engraving'],
  镀铬: ['镀铬', '退铬', 'chrome'],
  打样: ['打样', 'proofing'],
  检验: ['检验', 'inspection'],
  财务: ['财务', '会计', '出纳', '开票', '统计', 'finance', 'account'],
  送货: ['送货', '仓库', '仓储', '物流', 'delivery', 'warehouse']
}

const canStartWorkflow = computed(() => hasPermission('workflow_v2:start'))
const canOperateWorkflow = computed(() => hasPermission('workflow_v2:operate'))
const canAssignMaking = computed(() => hasPermission('workflow_v2:making:assign'))
const canOperateEpin = computed(() => hasPermission('workflow_v2:epin:operate'))
const canCreatePreOrder = computed(() => hasPermission('workflow_v2:pre_order:create'))
const canConfirmPreOrder = computed(() => hasPermission('workflow_v2:pre_order:confirm'))
const canConvertPreOrder = computed(() => hasPermission('workflow_v2:order:create'))
const canCreateAbnormalFlow = computed(() => hasPermission('workflow_v2:abnormal:create'))
const canApproveAbnormalFlow = computed(() => hasPermission('workflow_v2:abnormal:approve'))
const isWorkflowManager = computed(() => {
  const roles = session.user?.roles || []
  return roles.some((role) => ['admin', 'boss', 'production_manager'].includes(role)) || hasPermission('workflow_v2:template:manage')
})
const canBrowseOrders = computed(() => isWorkflowManager.value || hasPermission('workflow_v2:start') || hasPermission('workflow_v2:order:create'))
const canUsePreOrders = computed(() => isWorkflowManager.value || canCreatePreOrder.value || canConfirmPreOrder.value || canConvertPreOrder.value)
const canSeeMakingPanel = computed(() => isWorkflowManager.value || canAssignMaking.value || departmentMatchesCurrentUser('制作'))
const canSeeEpinPanel = computed(() => isWorkflowManager.value || (canOperateEpin.value && departmentMatchesCurrentUser('电拼')))

const displayNodes = computed<DisplayNode[]>(() => {
  if (graph.value) {
    return graph.value.nodes.map((node) => ({ ...node }))
  }
  return []
})

const activeNodes = computed(() =>
  (graph.value?.nodes || [])
    .filter((node) => node.is_current || ['active', 'in_progress', 'waiting'].includes(node.status))
    .sort((a, b) => a.sort_order - b.sort_order)
)
const abnormalStartNodeOptions = computed(() =>
  displayNodes.value
    .filter((node) => !['start', 'end'].includes(node.node_type) && !forbiddenAbnormalProcessNodes.has(node.node_code))
    .sort(sortNode)
)
const abnormalProcessNodeOptions = computed(() =>
  displayNodes.value
    .filter((node) => !['start', 'end'].includes(node.node_type) && !forbiddenAbnormalProcessNodes.has(node.node_code))
    .sort(sortNode)
)

const completedCount = computed(() => (graph.value?.nodes || []).filter((node) => node.status === 'completed').length)
const pendingCount = computed(() => (graph.value?.nodes || []).filter((node) => node.status === 'pending').length)
const pendingAbnormalCount = computed(() =>
  abnormalFlows.value.filter((item) => ['pending_approval', 'processing'].includes(item.status)).length
)
const orderQuantity = computed(() => {
  if (!selectedOrder.value) return 0
  return selectedOrder.value.items.reduce((sum, item) => sum + Number(item.quantity || 0), 0)
})
const assignedSets = computed(() => makingAssignments.value.reduce((sum, item) => sum + Number(item.assigned_sets || 0), 0))
const productionUsers = computed(() =>
  users.value.filter((user) => {
    if (user.status !== 'active') return false
    const roles = user.roles || []
    if (roles.includes('operator') || roles.includes('designer')) return true
    const department = String(user.department || '')
    return /制作|电拼|雕刻|卷板|磨|车床|镀|operator|Production|Carving/i.test(department) && !roles.includes('sales')
  })
)
const usersById = computed(() => new Map(users.value.map((user) => [user.id, user])))
const currentUserName = computed(() => session.user?.real_name || session.user?.username || '-')
const nodeActionDialogTitle = computed(() => (activeActionNode.value ? nodeCompleteActionText(activeActionNode.value) : '完成这一步'))
const nodeActionConfirmText = computed(() => {
  const nodeCode = activeActionNode.value?.node_code
  if (nodeCode === 'finance_bill') return '确认并放行'
  if (nodeCode === 'delivery') return '登记送货'
  if (nodeCode === 'sign') return '登记签收'
  return '完成这一步'
})

const metrics = computed(() => [
  {
    label: canBrowseOrders.value ? '订单列表' : '我的任务',
    value: canBrowseOrders.value ? orders.value.length : myTasks.value.length,
    note: canBrowseOrders.value ? '当前筛选结果' : '当前账号待处理'
  },
  {
    label: '跟进状态',
    value: graph.value ? '已启动' : '未启动',
    note: selectedOrder.value?.order_no || selectedSalesOrderId.value?.slice(0, 8) || '选择订单后查看'
  },
  {
    label: '当前待办',
    value: activeNodes.value.length,
    note: activeNodes.value.map((node) => node.node_name).join(' / ') || '-'
  },
  {
    label: '异常处理',
    value: pendingAbnormalCount.value,
    note: abnormalFlows.value.length ? `${abnormalFlows.value.length} 条记录` : '暂无异常'
  },
  {
    label: '已完成',
    value: completedCount.value,
    note: graph.value ? `待处理 ${pendingCount.value}` : '选择并启动订单后查看'
  },
  {
    label: '放行检查',
    value: joinCheck.value?.ready ? '满足' : '等待',
    note: joinWaitingText.value
  }
])

const flowSections = computed(() => {
  const nodes = displayNodes.value
  return [
    {
      key: 'making',
      title: '制作线',
      nodes: nodes.filter((node) => node.branch_code === 'making').sort(sortNode)
    },
    {
      key: 'processing',
      title: '加工线',
      nodes: nodes.filter((node) => node.branch_code === 'processing').sort(sortNode)
    },
    {
      key: 'post_join',
      title: '后续工序',
      nodes: nodes
        .filter((node) => !node.branch_code && node.node_code !== 'formal_order')
        .sort(sortNode)
    }
  ]
})

const joinLabel = computed(() => {
  if (!graph.value) return '未启动'
  return joinCheck.value?.ready ? '可进入电雕' : '等待前面完成'
})

const joinWaitingText = computed(() => {
  if (!graph.value) return '尚未开始'
  if (!joinCheck.value) return '还未检查'
  if (joinCheck.value.ready) return '已满足'
  return joinCheck.value.waiting_for.length ? joinCheck.value.waiting_for.join('、') : '等待前面工作'
})

const fulfillmentStageType = computed<'success' | 'warning' | 'info' | 'primary'>(() => {
  const stage = fulfillmentSummary.value?.current_stage
  if (stage === 'signed') return 'success'
  if (stage === 'released' || stage === 'shipped') return 'primary'
  if (stage === 'billing') return 'warning'
  return 'info'
})

function blankPreOrderForm(): PreOrderCreatePayload {
  return {
    sample_no: '',
    customer_id: undefined,
    customer_name: '',
    product_name: '',
    type: '',
    num: 1,
    print_color: '',
    remarks: ''
  }
}

function blankConvertForm(): ConvertPreOrderPayload {
  return {
    customer_id: undefined,
    due_date: '',
    priority: 'normal',
    unit_price: 0
  }
}

function blankAbnormalForm(): AbnormalFlowCreatePayload {
  return {
    abnormal_type: 'quality_rework',
    reason: '',
    selected_start_node: '',
    selected_process_nodes: [],
    need_inspection: true,
    need_finance_bill: false,
    need_delivery: false
  }
}

function blankNodeActionForm(): NodeActionForm {
  return {
    bill_no: '',
    delivery_note_no: '',
    bill_amount: 0,
    delivery_time: '',
    delivery_person: '',
    logistics: '',
    delivery_address: '',
    signer: '',
    signed_at: '',
    sign_proof_no: '',
    remarks: ''
  }
}

function sortNode(a: DisplayNode, b: DisplayNode) {
  return a.sort_order - b.sort_order
}

function normalizeText(value?: string) {
  return String(value || '').trim().toLowerCase()
}

function departmentMatchesCurrentUser(nodeDepartment?: string) {
  const userDepartment = normalizeText(session.user?.department)
  const nodeDepartmentText = normalizeText(nodeDepartment)
  if (!userDepartment || !nodeDepartmentText) return false
  if (userDepartment.includes(nodeDepartmentText) || nodeDepartmentText.includes(userDepartment)) return true
  const keywords = departmentKeywords[nodeDepartment || ''] || []
  return keywords.some((keyword) => userDepartment.includes(normalizeText(keyword)))
}

function canOperateNode(node: WorkflowNode | DisplayNode) {
  if (!canOperateWorkflow.value) return false
  if (isWorkflowManager.value) return true
  if (node.assigned_user_id && node.assigned_user_id === session.user?.id) return true
  if (node.node_code === 'making_dispatch') return canAssignMaking.value
  if (node.node_code === 'epin') return canOperateEpin.value && departmentMatchesCurrentUser('电拼')
  if (node.node_type === 'join') return hasPermission('workflow_v2:join:release')
  return departmentMatchesCurrentUser(node.department)
}

function currentActionText(node: WorkflowNode | DisplayNode) {
  if (node.waiting_reason) return node.waiting_reason
  if (node.status === 'waiting') return '等前面工作完成后再处理'
  if (node.node_code === 'making_dispatch') return '生产主管分配制作员工和套数'
  if (node.node_code === 'making_employee_task') return '制作员工完成后提交给电拼'
  if (node.node_code === 'epin') return '电拼接收并完成制作批次'
  if (node.node_code === 'join_before_engraving') return '确认电拼和铜磨都完成后放行'
  if (node.node_code === 'finance_bill') return '财务确认 Bill 和送货单号'
  if (node.node_code === 'delivery') return '登记送货时间、司机和物流信息'
  if (node.node_code === 'sign') return '登记客户签收'
  return `${node.department || '相关部门'}处理完成后点击完成`
}

function nodeHelpText(node: WorkflowNode | DisplayNode) {
  if (node.waiting_reason) return node.waiting_reason
  const map: Record<string, string> = {
    formal_order: '订单已确认',
    making_dispatch: '主管分配制作员工',
    making_employee_task: '制作完成后交电拼',
    epin: '电拼批次处理',
    roll_bending: '卷板加工',
    flange_plate: '法兰 / 法版加工',
    lathe: '车床加工',
    basic_grinding: '基磨 / 磨床加工',
    copper_plating: '镀铜处理',
    copper_grinding: '铜磨 / 研磨处理',
    join_before_engraving: '电拼和铜磨完成后放行',
    engraving: '电雕 / 雕刻',
    chrome_plating: '镀铬处理',
    proofing: '打样确认',
    inspection: '质检确认',
    finance_bill: '财务开 Bill 并放行',
    delivery: '送货登记',
    sign: '客户签收登记',
    completed: '订单完成'
  }
  return map[node.node_code] || `${node.department || '相关部门'}负责`
}

function nodeCompleteActionText(node: WorkflowNode | DisplayNode) {
  const map: Record<string, string> = {
    finance_bill: '确认 Bill 并放行',
    delivery: '登记送货',
    sign: '登记签收',
    join_before_engraving: '确认可电雕'
  }
  return map[node.node_code] || '完成这一步'
}

function isBusinessActionNode(node: WorkflowNode | DisplayNode) {
  return ['finance_bill', 'delivery', 'sign'].includes(node.node_code)
}

function nodeTagType(status: string) {
  const map: Record<string, 'success' | 'warning' | 'info' | 'primary' | 'danger'> = {
    completed: 'success',
    active: 'warning',
    in_progress: 'primary',
    waiting: 'danger',
    pending: 'info',
    template: 'info'
  }
  return map[status] || 'info'
}

function nodeStatusLabel(status: string) {
  const map: Record<string, string> = {
    pending: '未激活',
    active: '待处理',
    in_progress: '进行中',
    waiting: '等待',
    blocked: '阻塞',
    completed: '完成',
    skipped: '跳过',
    cancelled: '取消'
  }
  return map[status] || status
}

function workflowStatusLabel(status?: string) {
  const map: Record<string, string> = {
    running: '进行中',
    completed: '已完成',
    paused: '已暂停',
    cancelled: '已取消'
  }
  return status ? map[status] || status : '-'
}

function orderStatusLabel(status?: string) {
  return status ? statusLabel(orderStatusMap, status) : '-'
}

function orderStatusType(status: string): 'success' | 'warning' | 'info' | 'primary' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'primary' | 'danger'> = {
    confirmed: 'warning',
    in_production: 'primary',
    pending_delivery: 'warning',
    delivered: 'success',
    paid: 'success',
    archived: 'info',
    cancelled: 'danger',
    reworking: 'danger'
  }
  return map[status] || 'info'
}

function makingStatusLabel(status: string) {
  const map: Record<string, string> = {
    assigned: '已分配',
    processing: '制作中',
    completed: '已完成',
    submitted: '已提交电拼',
    recalled: '已撤回',
    cancelled: '已取消'
  }
  return map[status] || status
}

function epinStatusLabel(status: string) {
  const map: Record<string, string> = {
    submitted: '待接收',
    received: '已接收',
    processing: '电拼中',
    completed: '已完成',
    rejected: '已退回'
  }
  return map[status] || status
}

function billStatusLabel(status?: string) {
  const map: Record<string, string> = {
    pending: '待打印',
    printed: '已打印',
    released: '已放行',
    cancelled: '已取消'
  }
  return status ? map[status] || status : '等待财务处理'
}

function deliveryStatusLabel(status?: string) {
  const map: Record<string, string> = {
    draft: '待送货',
    shipped: '已送货',
    signed: '已签收',
    cancelled: '已取消'
  }
  return status ? map[status] || status : '等待送货'
}

function fulfillmentStageLabel(stage?: string) {
  const map: Record<string, string> = {
    production: '生产中',
    waiting_finance: '等待财务',
    billing: '财务处理中',
    released: '财务已放行',
    shipped: '已送货',
    signed: '已签收'
  }
  return stage ? map[stage] || stage : '暂无记录'
}

function formatAmount(amount?: number | null) {
  if (amount === undefined || amount === null) return '-'
  return Number(amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function preOrderStatusLabel(status: string) {
  const map: Record<string, string> = {
    submitted: '已提交',
    customer_approved: '客户已确认',
    customer_rejected: '客户驳回',
    converted: '已转订单',
    cancelled: '已取消'
  }
  return map[status] || status
}

function preOrderStatusType(status: string): 'success' | 'warning' | 'info' | 'primary' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'primary' | 'danger'> = {
    submitted: 'warning',
    customer_approved: 'success',
    customer_rejected: 'danger',
    converted: 'primary',
    cancelled: 'info'
  }
  return map[status] || 'info'
}

function abnormalTypeLabel(type: string) {
  const map: Record<string, string> = {
    quality_rework: '质量返工',
    customer_change: '客户变更',
    production_exception: '生产异常',
    supplement: '补做'
  }
  return map[type] || type
}

function abnormalStatusLabel(status: string) {
  const map: Record<string, string> = {
    pending_approval: '待审批',
    approved: '已批准',
    processing: '处理中',
    completed: '已完成',
    rejected: '已驳回',
    cancelled: '已取消'
  }
  return map[status] || status
}

function abnormalStatusType(status: string): 'success' | 'warning' | 'info' | 'primary' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'primary' | 'danger'> = {
    pending_approval: 'warning',
    approved: 'primary',
    processing: 'primary',
    completed: 'success',
    rejected: 'danger',
    cancelled: 'info'
  }
  return map[status] || 'info'
}

function workflowNodeLabel(nodeCode?: string) {
  if (!nodeCode) return '-'
  const node = displayNodes.value.find((item) => item.node_code === nodeCode)
  if (!node) return nodeCode
  return `${node.node_name}${node.department ? ` · ${node.department}` : ''}`
}

function abnormalProcessText(nodeCodes: string[]) {
  if (!nodeCodes.length) return '-'
  return nodeCodes.map((nodeCode) => workflowNodeLabel(nodeCode)).join(' / ')
}

function canApprovePreOrder(preOrder: PreOrder) {
  return !['customer_approved', 'converted', 'cancelled'].includes(preOrder.status)
}

function canRejectPreOrder(preOrder: PreOrder) {
  return !['customer_rejected', 'converted', 'cancelled'].includes(preOrder.status)
}

function userLabel(userId?: string) {
  if (!userId) return '-'
  const user = usersById.value.get(userId)
  if (!user) return userId.slice(0, 8)
  return `${user.real_name || user.username}${user.department ? ` · ${user.department}` : ''}`
}

function customerLabel(customer: Customer) {
  return `${customer.customer_code} · ${customer.name}`
}

function errorMessage(error: unknown) {
  const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail) return JSON.stringify(detail)
  return '操作失败'
}

async function loadUsers() {
  try {
    const { data } = await apiClient.get<UserOption[]>('/users/options')
    users.value = data
  } catch {
    users.value = []
  }
}

async function loadCustomers(keyword = '') {
  if (!hasPermission('customer:view')) {
    customers.value = []
    return
  }
  try {
    const pageSize = 100
    let page = 1
    const items: Customer[] = []
    while (true) {
      const { data } = await apiClient.get<PageResponse<Customer>>('/customers', {
        params: {
          keyword: keyword || undefined,
          page,
          page_size: pageSize
        }
      })
      items.push(...data.items)
      if (items.length >= data.total || data.items.length === 0) break
      page += 1
    }
    customers.value = sortCustomersForCurrentUser(items, session.user)
  } catch {
    customers.value = []
  }
}

function handleCustomerDropdown(visible: boolean) {
  if (visible && !customers.value.length) void loadCustomers()
}

function syncPreOrderCustomerName(customerId?: string) {
  const customer = customers.value.find((item) => item.id === customerId)
  if (customer) preOrderForm.value.customer_name = customer.name
}

function openPreOrderDialog() {
  preOrderForm.value = blankPreOrderForm()
  preOrderDialogVisible.value = true
  void loadCustomers()
}

function openConvertDialog(preOrder: PreOrder) {
  selectedPreOrder.value = preOrder
  convertForm.value = {
    ...blankConvertForm(),
    customer_id: preOrder.customer_id || undefined
  }
  convertDialogVisible.value = true
  void loadCustomers()
}

function optionalText(value?: string) {
  const text = String(value || '').trim()
  return text || undefined
}

async function loadPreOrders() {
  if (!canUsePreOrders.value) {
    preOrders.value = []
    return
  }
  preOrdersLoading.value = true
  try {
    const { data } = await apiClient.get<PageResponse<PreOrder>>('/workflow-v2/pre-orders', {
      params: {
        keyword: preOrderKeyword.value || undefined,
        status_filter: preOrderStatusFilter.value || undefined,
        page: 1,
        page_size: 20
      }
    })
    preOrders.value = data.items
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    preOrdersLoading.value = false
  }
}

async function submitPreOrder() {
  const payload: PreOrderCreatePayload = {
    sample_no: preOrderForm.value.sample_no.trim(),
    customer_id: preOrderForm.value.customer_id || undefined,
    customer_name: preOrderForm.value.customer_name.trim(),
    product_name: preOrderForm.value.product_name.trim(),
    type: optionalText(preOrderForm.value.type),
    num: Number(preOrderForm.value.num || 0),
    print_color: optionalText(preOrderForm.value.print_color),
    remarks: optionalText(preOrderForm.value.remarks)
  }
  if (!payload.sample_no || !payload.customer_name || !payload.product_name || payload.num <= 0) {
    ElMessage.warning('请填写样稿号、客户、产品和套数')
    return
  }

  creatingPreOrder.value = true
  try {
    await apiClient.post<PreOrder>('/workflow-v2/pre-orders', payload)
    preOrderDialogVisible.value = false
    await loadPreOrders()
    ElMessage.success('预订单已保存')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    creatingPreOrder.value = false
  }
}

async function approvePreOrder(preOrder: PreOrder) {
  if (!canConfirmPreOrder.value || !canApprovePreOrder(preOrder)) return
  try {
    await apiClient.post<PreOrder>(`/workflow-v2/pre-orders/${preOrder.id}/approve-customer`, {})
    await loadPreOrders()
    ElMessage.success('客户确认已通过')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function rejectPreOrder(preOrder: PreOrder) {
  if (!canConfirmPreOrder.value || !canRejectPreOrder(preOrder)) return
  try {
    await apiClient.post<PreOrder>(`/workflow-v2/pre-orders/${preOrder.id}/reject-customer`, {})
    await loadPreOrders()
    ElMessage.success('客户确认已驳回')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function submitConvertPreOrder() {
  if (!selectedPreOrder.value || !canConvertPreOrder.value) return
  const customerId = convertForm.value.customer_id || selectedPreOrder.value.customer_id
  if (!customerId || !convertForm.value.due_date) {
    ElMessage.warning('请选择客户并填写交期')
    return
  }
  convertingPreOrder.value = true
  try {
    const { data } = await apiClient.post<{ sales_order_id: string; order_no: string }>(
      `/workflow-v2/pre-orders/${selectedPreOrder.value.id}/convert`,
      {
        customer_id: customerId,
        due_date: convertForm.value.due_date,
        priority: convertForm.value.priority,
        unit_price: Number(convertForm.value.unit_price || 0),
        route_id: convertForm.value.route_id || undefined
      }
    )
    convertDialogVisible.value = false
    await loadPreOrders()
    if (canBrowseOrders.value) await loadOrders()
    ElMessage.success(`已转为订单 ${data.order_no}`)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    convertingPreOrder.value = false
  }
}

function openAbnormalDialog() {
  abnormalForm.value = blankAbnormalForm()
  const currentNode = activeNodes.value.find((node) => node.is_current) || activeNodes.value[0] || abnormalStartNodeOptions.value[0]
  if (currentNode) {
    abnormalForm.value.selected_start_node = currentNode.node_code
    abnormalForm.value.selected_process_nodes = [currentNode.node_code].filter(
      (nodeCode) => !forbiddenAbnormalProcessNodes.has(nodeCode)
    )
  }
  abnormalDialogVisible.value = true
}

async function loadAbnormalFlows() {
  if (!selectedSalesOrderId.value) {
    abnormalFlows.value = []
    return
  }
  try {
    const { data } = await apiClient.get<AbnormalFlow[]>(`/workflow-v2/sales-orders/${selectedSalesOrderId.value}/abnormal-flows`)
    abnormalFlows.value = data
  } catch (error) {
    const status = (error as { response?: { status?: number } }).response?.status
    if (status === 404 || status === 403) {
      abnormalFlows.value = []
      return
    }
    ElMessage.error(errorMessage(error))
  }
}

async function submitAbnormalFlow() {
  if (!selectedSalesOrderId.value || !canCreateAbnormalFlow.value) return
  if (!graph.value) {
    ElMessage.warning('请先开始跟进生产')
    return
  }
  const payload: AbnormalFlowCreatePayload = {
    abnormal_type: abnormalForm.value.abnormal_type,
    reason: abnormalForm.value.reason.trim(),
    selected_start_node: abnormalForm.value.selected_start_node,
    selected_process_nodes: abnormalForm.value.selected_process_nodes.filter(
      (nodeCode) => !forbiddenAbnormalProcessNodes.has(nodeCode)
    ),
    need_inspection: abnormalForm.value.need_inspection,
    need_finance_bill: abnormalForm.value.need_finance_bill,
    need_delivery: abnormalForm.value.need_delivery
  }
  if (!payload.abnormal_type || !payload.reason || !payload.selected_start_node || !payload.selected_process_nodes.length) {
    ElMessage.warning('请填写异常类型、开始步骤、需要重做的步骤和原因')
    return
  }
  creatingAbnormalFlow.value = true
  try {
    await apiClient.post<AbnormalFlow>(`/workflow-v2/sales-orders/${selectedSalesOrderId.value}/abnormal-flow`, payload)
    abnormalDialogVisible.value = false
    await loadAbnormalFlows()
    ElMessage.success('异常处理已提交')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    creatingAbnormalFlow.value = false
  }
}

async function approveAbnormalFlow(record: AbnormalFlow) {
  if (!canApproveAbnormalFlow.value || record.status !== 'pending_approval') return
  operatingAbnormalFlowId.value = record.id
  try {
    await apiClient.post<AbnormalFlow>(`/workflow-v2/abnormal-flows/${record.id}/approve`, {})
    await loadAbnormalFlows()
    await loadGraph()
    ElMessage.success('异常返工已批准')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    operatingAbnormalFlowId.value = null
  }
}

async function rejectAbnormalFlow(record: AbnormalFlow) {
  if (!canApproveAbnormalFlow.value || record.status !== 'pending_approval') return
  operatingAbnormalFlowId.value = record.id
  try {
    await apiClient.post<AbnormalFlow>(`/workflow-v2/abnormal-flows/${record.id}/reject`, {})
    await loadAbnormalFlows()
    ElMessage.success('异常处理已驳回')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    operatingAbnormalFlowId.value = null
  }
}

async function completeAbnormalFlow(record: AbnormalFlow) {
  if (!canApproveAbnormalFlow.value || record.status !== 'processing') return
  operatingAbnormalFlowId.value = record.id
  try {
    await apiClient.post<AbnormalFlow>(`/workflow-v2/abnormal-flows/${record.id}/complete`, {})
    await loadAbnormalFlows()
    ElMessage.success('异常处理已完成')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    operatingAbnormalFlowId.value = null
  }
}

async function loadOrders() {
  if (!canBrowseOrders.value) return
  const { data } = await apiClient.get<PageResponse<SalesOrder>>('/sales-orders', {
    params: {
      keyword: keyword.value || undefined,
      status_filter: statusFilter.value || undefined,
      include_history: historicalOrderStatuses.has(statusFilter.value),
      page: 1,
      page_size: 30
    }
  })
  orders.value = data.items
  if (selectedOrder.value && !orders.value.some((order) => order.id === selectedOrder.value?.id)) {
    selectedOrder.value = null
    selectedSalesOrderId.value = null
    graph.value = null
    joinCheck.value = null
    fulfillmentSummary.value = null
    makingAssignments.value = []
    epinBatches.value = []
    abnormalFlows.value = []
  }
  if (!selectedOrder.value && orders.value.length) {
    await selectOrder(orders.value[0])
  }
}

async function selectOrder(order: SalesOrder) {
  selectedOrder.value = order
  selectedSalesOrderId.value = order.id
  graph.value = null
  joinCheck.value = null
  fulfillmentSummary.value = null
  makingAssignments.value = []
  epinBatches.value = []
  abnormalFlows.value = []
  await loadGraph()
}

async function loadMyTasks() {
  const { data } = await apiClient.get<WorkflowNode[]>('/workflow-v2/tasks/my')
  myTasks.value = data
  if (!selectedSalesOrderId.value && data.length) {
    await selectTask(data[0])
  }
}

async function selectTask(task: WorkflowNode) {
  selectedOrder.value = null
  selectedSalesOrderId.value = task.sales_order_id
  graph.value = null
  joinCheck.value = null
  fulfillmentSummary.value = null
  makingAssignments.value = []
  epinBatches.value = []
  abnormalFlows.value = []
  await loadGraph()
}

async function loadGraph() {
  if (!selectedSalesOrderId.value) return
  try {
    const { data } = await apiClient.get<WorkflowGraph>(`/workflow-v2/sales-orders/${selectedSalesOrderId.value}/graph`)
    graph.value = data
    await loadJoinCheck()
    await loadFulfillmentSummary()
    await loadMakingData()
    await loadAbnormalFlows()
  } catch (error) {
    const status = (error as { response?: { status?: number } }).response?.status
    if (status === 404) {
      graph.value = null
      joinCheck.value = null
      fulfillmentSummary.value = null
      makingAssignments.value = []
      epinBatches.value = []
      await loadAbnormalFlows()
      return
    }
    ElMessage.error(errorMessage(error))
  }
}

async function loadFulfillmentSummary() {
  if (!selectedSalesOrderId.value || !graph.value) {
    fulfillmentSummary.value = null
    return
  }
  try {
    const { data } = await apiClient.get<WorkflowFulfillmentSummary>(
      `/workflow-v2/sales-orders/${selectedSalesOrderId.value}/fulfillment-summary`
    )
    fulfillmentSummary.value = data
  } catch (error) {
    const status = (error as { response?: { status?: number } }).response?.status
    if (status === 404 || status === 403) {
      fulfillmentSummary.value = null
      return
    }
    ElMessage.error(errorMessage(error))
  }
}

async function loadJoinCheck() {
  if (!selectedSalesOrderId.value || !graph.value) return
  const { data } = await apiClient.get<WorkflowJoinCheck>(`/workflow-v2/sales-orders/${selectedSalesOrderId.value}/check-join`)
  joinCheck.value = data
}

async function loadMakingData() {
  if (!selectedSalesOrderId.value || !graph.value) return
  const requests: Promise<void>[] = []
  if (canSeeMakingPanel.value) {
    requests.push(
      apiClient
        .get<MakingAssignment[]>(`/workflow-v2/sales-orders/${selectedSalesOrderId.value}/making-assignments`)
        .then((response) => {
          makingAssignments.value = response.data
        })
    )
  } else {
    makingAssignments.value = []
  }
  if (canSeeEpinPanel.value) {
    requests.push(
      apiClient.get<EpinBatch[]>(`/workflow-v2/sales-orders/${selectedSalesOrderId.value}/epin-batches`).then((response) => {
        epinBatches.value = response.data
      })
    )
  } else {
    epinBatches.value = []
  }
  await Promise.all(requests)
  for (const assignment of makingAssignments.value) {
    const remaining = Math.max(1, Number(assignment.assigned_sets || 0) - Number(assignment.completed_sets || 0))
    completionByAssignment.value[assignment.id] ||= remaining
  }
}

function addAssignmentDraft() {
  assignmentDrafts.value.push({ employee_id: '', assigned_sets: 1, remarks: '' })
}

function removeAssignmentDraft(index: number) {
  assignmentDrafts.value.splice(index, 1)
}

function resetAssignmentDrafts() {
  assignmentDrafts.value = [{ employee_id: '', assigned_sets: 1, remarks: '' }]
}

async function submitAssignments() {
  if (!selectedSalesOrderId.value || !canAssignMaking.value) return
  const assignments = assignmentDrafts.value
    .filter((item) => item.employee_id && item.assigned_sets > 0)
    .map((item) => ({
      employee_id: item.employee_id,
      assigned_sets: item.assigned_sets,
      remarks: item.remarks || undefined
    }))
  if (!assignments.length) {
    ElMessage.warning('请选择员工并填写分配套数')
    return
  }
  assigning.value = true
  try {
    await apiClient.post(`/workflow-v2/sales-orders/${selectedSalesOrderId.value}/making-assignments`, {
      assignments,
      allow_over_assign: false
    })
    resetAssignmentDrafts()
    await loadGraph()
    ElMessage.success('制作派工已保存')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    assigning.value = false
  }
}

async function completeAssignment(assignment: MakingAssignment) {
  const completedSets = completionByAssignment.value[assignment.id] || 0
  if (completedSets <= 0) {
    ElMessage.warning('请填写本次完成套数')
    return
  }
  try {
    await apiClient.post(`/workflow-v2/making-assignments/${assignment.id}/complete`, {
      completed_sets: completedSets
    })
    await loadGraph()
    ElMessage.success('制作完成数已提交')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function submitAssignmentToEpin(assignment: MakingAssignment) {
  try {
    await apiClient.post(`/workflow-v2/making-assignments/${assignment.id}/submit-epin`, {})
    await loadGraph()
    ElMessage.success('已提交到电拼')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function receiveEpin(batch: EpinBatch) {
  if (!canOperateEpin.value) return
  try {
    await apiClient.post(`/workflow-v2/epin-batches/${batch.id}/receive`, {})
    await loadGraph()
    ElMessage.success('电拼批次已接收')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function completeEpin(batch: EpinBatch) {
  if (!canOperateEpin.value) return
  try {
    await apiClient.post(`/workflow-v2/epin-batches/${batch.id}/complete`, {})
    await loadGraph()
    ElMessage.success('电拼批次已完成')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function startWorkflow() {
  if (!selectedOrder.value) return
  starting.value = true
  try {
    const { data } = await apiClient.post<WorkflowGraph>(`/workflow-v2/sales-orders/${selectedOrder.value.id}/start`, {})
    graph.value = data
    await loadJoinCheck()
    await loadFulfillmentSummary()
    await loadMakingData()
    ElMessage.success('已开始跟进生产')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    starting.value = false
  }
}

async function startNode(node: WorkflowNode | DisplayNode) {
  if (!node.id) return
  operatingNodeId.value = node.id
  try {
    await apiClient.post(`/workflow-v2/nodes/${node.id}/start`, {})
    await loadGraph()
    ElMessage.success('这一步已开始')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    operatingNodeId.value = null
  }
}

function handleCompleteNode(node: WorkflowNode | DisplayNode) {
  if (isBusinessActionNode(node)) {
    openNodeActionDialog(node)
    return
  }
  void completeNode(node)
}

function openNodeActionDialog(node: WorkflowNode | DisplayNode) {
  if (!node.id) return
  activeActionNode.value = node
  nodeActionForm.value = {
    ...blankNodeActionForm(),
    delivery_person: currentUserName.value === '-' ? '' : currentUserName.value
  }
  nodeActionDialogVisible.value = true
}

function compactRemarks(entries: Array<[string, string | number | undefined]>) {
  return entries
    .map(([label, value]) => [label, String(value ?? '').trim()] as const)
    .filter(([, value]) => value.length > 0 && value !== '0')
    .map(([label, value]) => `${label}：${value}`)
    .join('；')
}

function buildNodeActionRemarks(node: WorkflowNode | DisplayNode) {
  const form = nodeActionForm.value
  if (node.node_code === 'finance_bill') {
    return compactRemarks([
      ['Bill 编号', form.bill_no],
      ['送货单号', form.delivery_note_no],
      ['Bill 金额', form.bill_amount],
      ['放行人', currentUserName.value],
      ['说明', form.remarks]
    ])
  }
  if (node.node_code === 'delivery') {
    return compactRemarks([
      ['送货时间', form.delivery_time],
      ['送货人/司机', form.delivery_person],
      ['物流/车号', form.logistics],
      ['客户地址', form.delivery_address],
      ['备注', form.remarks]
    ])
  }
  if (node.node_code === 'sign') {
    return compactRemarks([
      ['签收人', form.signer],
      ['签收时间', form.signed_at],
      ['签收单号/凭证', form.sign_proof_no],
      ['登记人', currentUserName.value],
      ['备注', form.remarks]
    ])
  }
  return form.remarks.trim()
}

function buildNodeActionPayload(node: WorkflowNode | DisplayNode) {
  const form = nodeActionForm.value
  const remarks = buildNodeActionRemarks(node)
  if (node.node_code === 'finance_bill') {
    return {
      remarks,
      bill_no: form.bill_no.trim(),
      delivery_note_no: form.delivery_note_no.trim(),
      bill_amount: form.bill_amount
    }
  }
  if (node.node_code === 'delivery') {
    return {
      remarks,
      delivery_time: form.delivery_time,
      delivery_person: form.delivery_person.trim(),
      logistics: form.logistics.trim() || undefined,
      delivery_address: form.delivery_address.trim() || undefined
    }
  }
  if (node.node_code === 'sign') {
    return {
      remarks,
      signer: form.signer.trim(),
      signed_at: form.signed_at,
      sign_proof_no: form.sign_proof_no.trim() || undefined
    }
  }
  return remarks ? { remarks } : {}
}

function validateNodeAction(node: WorkflowNode | DisplayNode) {
  const form = nodeActionForm.value
  if (node.node_code === 'finance_bill' && (!form.bill_no.trim() || !form.delivery_note_no.trim())) {
    ElMessage.warning('请填写 Bill 编号和送货单号')
    return false
  }
  if (node.node_code === 'delivery' && (!form.delivery_time || !form.delivery_person.trim())) {
    ElMessage.warning('请填写送货时间和送货人')
    return false
  }
  if (node.node_code === 'sign' && (!form.signer.trim() || !form.signed_at)) {
    ElMessage.warning('请填写签收人和签收时间')
    return false
  }
  return true
}

async function submitNodeAction() {
  const node = activeActionNode.value
  if (!node?.id || !validateNodeAction(node)) return
  nodeActionSubmitting.value = true
  try {
    const completed = await completeNode(node, buildNodeActionPayload(node))
    if (completed) {
      nodeActionDialogVisible.value = false
      activeActionNode.value = null
    }
  } finally {
    nodeActionSubmitting.value = false
  }
}

async function completeNode(node: WorkflowNode | DisplayNode, payload: Record<string, unknown> = {}) {
  if (!node.id) return false
  operatingNodeId.value = node.id
  try {
    await apiClient.post(`/workflow-v2/nodes/${node.id}/complete`, payload)
    await loadGraph()
    ElMessage.success(`${nodeCompleteActionText(node)}成功`)
    return true
  } catch (error) {
    ElMessage.error(errorMessage(error))
    return false
  } finally {
    operatingNodeId.value = null
  }
}

async function reloadAll() {
  loading.value = true
  try {
    const requests = [loadUsers(), canBrowseOrders.value ? loadOrders() : loadMyTasks()]
    if (canUsePreOrders.value) requests.push(loadPreOrders())
    await Promise.all(requests)
    if (selectedSalesOrderId.value) await loadGraph()
  } finally {
    loading.value = false
  }
}

function goOrderDetail() {
  if (selectedOrder.value) router.push(`/orders/${selectedOrder.value.id}`)
}

onMounted(reloadAll)
</script>

<style scoped>
.workflow-layout {
  display: grid;
  grid-template-columns: minmax(360px, 0.42fr) minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.workflow-order-panel,
.workflow-sidebar,
.pre-order-panel,
.workflow-main,
.workflow-graph-card {
  min-width: 0;
}

.workflow-sidebar {
  display: grid;
  gap: 18px;
  align-content: start;
}

.workflow-main {
  display: grid;
  gap: 18px;
}

.making-epin-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  gap: 18px;
}

.assignment-editor {
  display: grid;
  gap: 10px;
  margin-bottom: 14px;
}

.assignment-draft {
  display: grid;
  grid-template-columns: minmax(150px, 1fr) 110px minmax(140px, 1fr) 58px;
  gap: 10px;
  align-items: center;
}

.assignment-number,
.inline-number {
  width: 100%;
}

.assignment-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.account-scope {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.pre-order-filters {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 132px 44px;
  gap: 10px;
  margin-bottom: 14px;
}

.stacked-cell {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.stacked-cell strong,
.stacked-cell span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stacked-cell span {
  color: #667085;
  font-size: 12px;
}

.workflow-order-filters {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 140px 44px;
  gap: 10px;
  margin-bottom: 14px;
}

.pre-order-form :deep(.el-select),
.pre-order-form :deep(.el-date-editor.el-input) {
  width: 100%;
}

.form-grid {
  display: grid;
  gap: 12px;
}

.form-grid.two-columns {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.full-width {
  width: 100%;
}

.abnormal-switches {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 18px;
}

.selected-order {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr)) auto;
  gap: 14px;
  align-items: center;
}

.selected-order > div {
  min-width: 0;
}

.selected-order strong {
  display: block;
  margin-top: 6px;
  overflow-wrap: anywhere;
}

.muted-label {
  color: #667085;
  font-size: 13px;
}

.workflow-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.next-action-list {
  display: grid;
  gap: 10px;
}

.next-action-item {
  display: grid;
  grid-template-columns: minmax(220px, 0.9fr) minmax(180px, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 12px;
  border: 1px solid #e5edf5;
  border-radius: 8px;
  background: #ffffff;
}

.next-action-item.node-active,
.next-action-item.node-in_progress {
  border-color: #fed7aa;
  background: #fffaf0;
}

.next-action-item.node-waiting {
  border-color: #fecaca;
  background: #fff7ed;
}

.next-action-main {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.next-action-main div {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.next-action-main strong,
.next-action-main span,
.next-action-note {
  overflow-wrap: anywhere;
}

.next-action-main span,
.next-action-note {
  color: #667085;
  font-size: 13px;
}

.next-action-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.fulfillment-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.fulfillment-step {
  min-height: 112px;
  display: grid;
  gap: 6px;
  align-content: center;
  padding: 14px;
  border: 1px solid #e5edf5;
  border-radius: 8px;
  background: #f8fafc;
  min-width: 0;
}

.fulfillment-step.active {
  border-color: #bfdbfe;
  background: #eff6ff;
}

.fulfillment-step.done {
  border-color: #b7ebcf;
  background: #f6ffed;
}

.fulfillment-step span,
.fulfillment-step small {
  color: #667085;
  font-size: 13px;
  overflow-wrap: anywhere;
}

.fulfillment-step strong {
  color: #18212f;
  overflow-wrap: anywhere;
}

.join-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.join-grid > div {
  min-height: 84px;
  display: grid;
  gap: 6px;
  align-content: center;
  padding: 14px;
  border: 1px solid #e5edf5;
  border-radius: 8px;
  background: #f8fafc;
}

.join-grid > div.done {
  border-color: #b7ebcf;
  background: #f6ffed;
}

.join-icon {
  width: 18px;
  height: 18px;
  color: #0f766e;
}

.join-reason .join-icon {
  color: #d97706;
}

.join-grid span {
  color: #667085;
  font-size: 13px;
}

.join-grid strong {
  color: #18212f;
}

.workflow-sections {
  display: grid;
  gap: 18px;
}

.workflow-section {
  display: grid;
  gap: 10px;
}

.workflow-section-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.workflow-node-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(176px, 1fr));
  gap: 12px;
}

.workflow-node-row.empty {
  display: block;
}

.workflow-node {
  min-height: 132px;
  display: grid;
  gap: 8px;
  align-content: start;
  padding: 12px;
  border: 1px solid #e5edf5;
  border-radius: 8px;
  background: #ffffff;
}

.workflow-node.current {
  border-color: #f59e0b;
  box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.14);
}

.workflow-node.node-completed {
  background: #f6ffed;
  border-color: #b7ebcf;
}

.workflow-node.node-active,
.workflow-node.node-in_progress {
  background: #fffaf0;
}

.workflow-node.node-waiting {
  background: #fff7ed;
  border-color: #fed7aa;
}

.node-head,
.node-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.node-head span,
.workflow-node small {
  color: #667085;
  font-size: 12px;
  overflow-wrap: anywhere;
}

.workflow-node strong {
  color: #18212f;
  overflow-wrap: anywhere;
}

@media (max-width: 1100px) {
  .workflow-layout,
  .selected-order,
  .next-action-item,
  .fulfillment-grid,
  .join-grid,
  .making-epin-grid,
  .assignment-draft,
  .form-grid.two-columns {
    grid-template-columns: 1fr;
  }

  .workflow-order-filters,
  .pre-order-filters {
    grid-template-columns: 1fr;
  }

  .workflow-actions {
    justify-content: flex-start;
  }
}
</style>
