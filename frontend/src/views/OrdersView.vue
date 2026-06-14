<template>
  <section class="page-stack">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-select v-model="statusFilter" placeholder="订单状态" clearable>
          <el-option label="草稿" value="draft" />
          <el-option label="已确认" value="confirmed" />
          <el-option label="生产中" value="in_production" />
          <el-option v-if="canViewHistory" label="已收款" value="paid" />
          <el-option v-if="canViewHistory" label="历史归档" value="archived" />
        </el-select>
        <el-select v-model="orderTypeFilter" placeholder="订单类型" clearable>
          <el-option v-for="type in orderTypeOptions" :key="type.value" :label="type.label" :value="type.value" />
        </el-select>
        <el-input
          v-model="keyword"
          class="order-search"
          clearable
          :prefix-icon="Search"
          placeholder="Order no / customer / product"
          @keyup.enter="loadOrders"
        />
        <el-button :icon="Refresh" @click="loadOrders">刷新</el-button>
      </div>
      <div class="toolbar-left">
        <el-button type="success" :icon="Download" v-permission="'report:export'" @click="exportOrders">
          导出 Excel
        </el-button>
        <el-button type="primary" :icon="Plus" v-permission="'order:create'" @click="openCreateDrawer">新建委托书</el-button>
      </div>
    </div>

    <el-card shadow="never" class="table-card">
      <el-table :data="orders" stripe @row-dblclick="goDetail">
        <el-table-column prop="order_no" label="订单编号" min-width="190">
          <template #default="{ row }">
            <el-button class="order-no-link" text type="primary" @click.stop="goDetail(row)">
              {{ row.order_no }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="170" show-overflow-tooltip>
          <template #default="{ row }">{{ orderTypeLabel(row.plate_details?.order_type) }}</template>
        </el-table-column>
        <el-table-column prop="product_summary" label="产品" min-width="180" />
        <el-table-column prop="due_date" label="交期" width="130" />
        <el-table-column prop="total_amount" label="金额" width="130">
          <template #default="{ row }">{{ formatCurrency(row.total_amount) }}</template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="110" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag>{{ statusLabel(orderStatusMap, row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <div class="order-row-actions">
              <el-button text type="primary" @click.stop="goEntrust(row)">委托书</el-button>
              <el-button text type="primary" @click.stop="printProductionOrder(row)">生产单</el-button>
              <el-button text type="danger" v-permission="'order:cancel'" @click.stop="deleteOrder(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="drawerVisible" title="新建委托书订单" size="74%" class="order-create-drawer">
      <el-form :model="form" label-position="top" class="order-form">
        <div class="form-grid">
          <el-form-item label="客户">
            <el-select v-model="form.customer_id" filterable placeholder="选择客户" @change="applyCustomer">
              <el-option v-for="customer in customers" :key="customer.id" :label="customer.name" :value="customer.id">
                <div class="customer-option">
                  <span>{{ customer.name }}</span>
                  <el-tag v-if="isCurrentUserCustomer(customer)" size="small" type="success" effect="plain">相关</el-tag>
                  <small>{{ customer.customer_code }}</small>
                </div>
              </el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="订单类型">
            <el-select v-model="form.plate_details.order_type" @change="applyOrderType">
              <el-option v-for="type in orderTypeOptions" :key="type.value" :label="type.label" :value="type.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="交期">
            <el-date-picker v-model="form.due_date" value-format="YYYY-MM-DD" type="date" placeholder="选择交期" />
          </el-form-item>
          <el-form-item label="优先级">
            <el-select v-model="form.priority">
              <el-option label="普通" value="normal" />
              <el-option label="加急" value="urgent" />
            </el-select>
          </el-form-item>
          <el-form-item label="Salesman">
            <el-select v-model="form.plate_details.salesman" filterable allow-create default-first-option clearable>
              <el-option v-for="user in users" :key="`salesman-${user.id}`" :label="user.real_name || user.username" :value="user.real_name || user.username" />
            </el-select>
          </el-form-item>
          <el-form-item label="Lister">
            <el-select v-model="form.plate_details.lister" filterable allow-create default-first-option clearable>
              <el-option v-for="user in users" :key="`lister-${user.id}`" :label="user.real_name || user.username" :value="user.real_name || user.username" />
            </el-select>
          </el-form-item>
        </div>

        <el-tabs v-model="activeCreateTab" class="order-tabs">
          <el-tab-pane label="基础信息" name="basic">
            <el-alert
              v-if="customerMaterials.length"
              type="warning"
              :closable="false"
              show-icon
              class="material-alert"
            >
              <template #title>
                客户已有来料 {{ customerMaterials.length }} 批，可优先调用：
                <span v-for="material in customerMaterials.slice(0, 4)" :key="material.id" class="material-pill">
                  {{ material.product_name }} {{ material.specification || '' }} · {{ material.quantity_on_hand }}{{ material.unit }}
                </span>
              </template>
            </el-alert>
            <div v-if="customerMaterials.length" class="material-use-grid">
              <el-form-item label="Customer Material">
                <el-select
                  v-model="selectedCustomerMaterialLotId"
                  clearable
                  filterable
                  placeholder="Select material lot"
                  @change="applyCustomerMaterialSelection"
                >
                  <el-option
                    v-for="material in customerMaterials"
                    :key="material.id"
                    :label="`${material.lot_no} · ${material.product_name} · ${material.quantity_on_hand}${material.unit}`"
                    :value="material.id"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="Use Qty">
                <el-input-number
                  v-model="customerMaterialUseQty"
                  :min="0"
                  :max="selectedCustomerMaterial ? selectedCustomerMaterial.quantity_on_hand : undefined"
                  :precision="3"
                  class="full-number"
                  @change="syncCustomerMaterialQty"
                />
              </el-form-item>
              <el-form-item v-if="selectedCustomerMaterial" label="Available">
                <el-tag type="info">
                  {{ selectedCustomerMaterial.quantity_on_hand }}{{ selectedCustomerMaterial.unit }}
                </el-tag>
              </el-form-item>
            </div>
            <el-alert
              v-if="customerPriceRules.length"
              type="info"
              :closable="false"
              show-icon
              class="customer-price-alert"
            >
              <template #title>
                <span>Customer price rules loaded: {{ customerPriceRules.length }}</span>
                <span v-if="customerPriceHint" class="customer-price-hint">{{ customerPriceHint }}</span>
                <el-button size="small" text type="primary" @click.stop="applyCustomerPriceToFirstItem(true)">
                  Apply Price
                </el-button>
              </template>
            </el-alert>
            <div class="plate-number-panel">
              <div class="panel-title">
                <span>Plate No.</span>
                <el-tag type="info">{{ availablePlateNumbers.length }} available</el-tag>
              </div>
              <div v-if="form.plate_details.order_type === 'new_cylinder'" class="plate-number-grid">
                <el-form-item label="Plate Type">
                  <el-select v-model="form.plate_details.plate_number_kind" @change="handlePlateKindChange">
                    <el-option v-for="type in plateNumberKindOptions" :key="type.value" :label="type.label" :value="type.value" />
                  </el-select>
                </el-form-item>
                <el-form-item label="Request QTY">
                  <el-input-number v-model="plateNumberRequestCount" :min="1" :max="50" class="full-number" />
                </el-form-item>
                <el-form-item label="Request">
                  <el-button type="primary" :loading="requestingPlateNumbers" @click="requestPlateNumbers">Request Plate No.</el-button>
                </el-form-item>
                <el-form-item label="Available Plate No." class="plate-number-select">
                  <el-select
                    v-model="form.plate_details.reserved_plate_number_id"
                    filterable
                    clearable
                    placeholder="Select available plate no."
                    @change="applyReservedPlateNumber"
                  >
                    <el-option v-for="plate in availablePlateNumbers" :key="plate.id" :label="plate.plate_no" :value="plate.id" />
                  </el-select>
                </el-form-item>
                <el-form-item label="Return">
                  <el-button :disabled="!form.plate_details.reserved_plate_number_id" @click="returnSelectedPlateNumber">Return Plate No.</el-button>
                </el-form-item>
              </div>
              <div v-else-if="form.plate_details.order_type === 'old_cylinder'" class="plate-number-grid derived-plate-grid">
                <el-form-item label="Original Plate No.">
                  <el-input v-model="form.plate_details.derived_source_cylinder_no" @change="loadDerivedPlatePreview" />
                </el-form-item>
                <el-form-item label="Generate Type">
                  <el-select v-model="form.plate_details.derivation_type" @change="loadDerivedPlatePreview">
                    <el-option v-for="type in revisionTypeOptions" :key="type.value" :label="type.label" :value="type.value" />
                  </el-select>
                </el-form-item>
                <el-form-item label="New Plate No.">
                  <el-input v-model="form.plate_details.cylinder_id" readonly />
                </el-form-item>
                <el-form-item label="Preview">
                  <el-button :loading="previewingPlateNumber" @click="loadDerivedPlatePreview">Preview Plate No.</el-button>
                </el-form-item>
              </div>
              <div v-else-if="form.plate_details.order_type === 'rework'" class="plate-number-grid derived-plate-grid">
                <el-form-item label="Original Plate No.">
                  <el-input v-model="form.plate_details.rework_source_cylinder_no" @change="loadDerivedPlatePreview" />
                </el-form-item>
                <el-form-item label="Rework Type">
                  <el-select v-model="form.plate_details.derivation_type" @change="loadDerivedPlatePreview">
                    <el-option v-for="type in reworkTypeOptions" :key="type.value" :label="type.label" :value="type.value" />
                  </el-select>
                </el-form-item>
                <el-form-item label="New Plate No.">
                  <el-input v-model="form.plate_details.cylinder_id" readonly />
                </el-form-item>
                <el-form-item label="Preview">
                  <el-button :loading="previewingPlateNumber" @click="loadDerivedPlatePreview">Preview Plate No.</el-button>
                </el-form-item>
              </div>
            </div>
            <div v-if="form.items[0]" class="quick-order-panel">
              <div class="panel-title">
                <span>快捷下单</span>
                <el-tag>合计 {{ formatCurrency(orderTotal) }}</el-tag>
              </div>
              <div class="quick-order-grid">
                <el-form-item label="产品模板">
                  <el-select
                    v-model="form.items[0].product_id"
                    clearable
                    filterable
                    placeholder="可选模板"
                    @change="applyProductTemplate(form.items[0])"
                  >
                    <el-option
                      v-for="product in products"
                      :key="product.id"
                      :label="`${product.product_code} · ${product.name}`"
                      :value="product.id"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="Product Name">
                  <el-input v-model="form.plate_details.product_name" @change="syncPlateToFirstItem" />
                </el-form-item>
                <el-form-item label="Total QTY">
                  <el-input v-model="form.plate_details.total_qty" @change="syncPlateToFirstItem" />
                </el-form-item>
                <el-form-item label="规格">
                  <el-input v-model="form.items[0].specification" placeholder="自动带入，可手动改" />
                </el-form-item>
                <el-form-item label="单位">
                  <el-input v-model="form.items[0].unit" />
                </el-form-item>
                <el-form-item label="单价">
                  <el-input-number v-model="form.items[0].unit_price" :min="0" :precision="2" class="full-number" />
                </el-form-item>
              </div>
            </div>
            <div v-if="false" class="field-grid">
              <el-form-item label="Unit L">
                <el-input v-model="form.plate_details.unit_l" @change="syncPlateDimensions" />
              </el-form-item>
              <el-form-item label="Straight">
                <el-select v-model="form.plate_details.straight" @change="syncPlateDimensions">
                  <el-option v-for="count in repeatCountOptions" :key="count" :label="count" :value="count" />
                </el-select>
              </el-form-item>
              <el-form-item label="Unit W">
                <el-input v-model="form.plate_details.unit_w" @change="syncPlateDimensions" />
              </el-form-item>
              <el-form-item label="Crossway">
                <el-select v-model="form.plate_details.crossway" @change="syncPlateDimensions">
                  <el-option v-for="count in repeatCountOptions" :key="count" :label="count" :value="count" />
                </el-select>
              </el-form-item>
              <el-form-item label="C">
                <el-input v-model="form.plate_details.c_value" readonly />
              </el-form-item>
              <el-form-item label="L">
                <el-input v-model="form.plate_details.l_value" readonly />
              </el-form-item>
              <el-form-item label="Cylinder Making">
                <el-select v-model="form.plate_details.cylinder_making">
                  <el-option v-for="option in cylinderMakingOptions" :key="option" :label="option" :value="option" />
                </el-select>
              </el-form-item>
              <el-form-item label="Dia">
                <el-input v-model="form.plate_details.dia" @change="syncDiaSeries" />
              </el-form-item>
              <el-form-item label="Increase">
                <el-input v-model="form.plate_details.increase" @change="syncDiaSeries" />
              </el-form-item>
              <el-form-item label="Original No">
                <el-input v-model="form.plate_details.original_no" />
              </el-form-item>
              <el-form-item label="B/O">
                <el-input v-model="form.plate_details.no" />
              </el-form-item>
              <el-form-item label="SampleNO">
                <el-input v-model="form.plate_details.sample_no" />
              </el-form-item>
              <el-form-item label="Order Time">
                <el-input v-model="form.plate_details.order_datetime" disabled />
              </el-form-item>
              <el-form-item label="Printing Method">
                <el-select v-model="form.plate_details.printing_method">
                  <el-option v-for="option in printingMethodOptions" :key="option" :label="option" :value="option" />
                </el-select>
              </el-form-item>
              <el-form-item label="Printing Material">
                <el-select v-model="form.plate_details.printing_material">
                  <el-option v-for="option in printingMaterialOptions" :key="option" :label="option" :value="option" />
                </el-select>
              </el-form-item>
              <el-form-item label="Material">
                <el-select v-model="form.plate_details.new_material" @change="syncMaterialFields">
                  <el-option v-for="option in materialSupplyOptions" :key="option.value" :label="option.label" :value="option.value" />
                </el-select>
              </el-form-item>
              <el-form-item v-if="form.plate_details.new_material === 'new+self-bring'" label="New QTY">
                <el-input v-model="form.plate_details.new_qty" inputmode="numeric" @change="syncMaterialFields" />
              </el-form-item>
              <el-form-item v-if="form.plate_details.new_material === 'new+self-bring'" label="Self-bring QTY">
                <el-input v-model="form.plate_details.self_bring_qty" inputmode="numeric" @change="syncMaterialFields" />
              </el-form-item>
              <el-form-item label="Sign-in Person">
                <el-input v-model="form.plate_details.sign_in_person" />
              </el-form-item>
              <el-form-item label="SalesMan">
                <el-input v-model="form.plate_details.salesman" />
              </el-form-item>
              <el-form-item label="Address" class="wide-field">
                <el-input v-model="form.plate_details.address" />
              </el-form-item>
            </div>
          </el-tab-pane>

          <el-tab-pane v-if="false" label="版胚" name="plate">
            <div class="field-grid">
              <el-form-item label="Flange Width">
                <el-input v-model="form.plate_details.flange" />
              </el-form-item>
              <el-form-item label="Flange Hole">
                <el-input v-model="form.plate_details.hole" />
              </el-form-item>
              <el-form-item label="Flange Slope">
                <el-input v-model="form.plate_details.slope" />
              </el-form-item>
              <el-form-item label="Copper Thickness">
                <el-input v-model="form.plate_details.copper_thickness" />
              </el-form-item>
              <el-form-item label="Key Way">
                <el-input v-model="form.plate_details.key_way" />
              </el-form-item>
              <el-form-item label="Dynamic Balance">
                <el-input v-model="form.plate_details.dynamic_balance" />
              </el-form-item>
              <el-form-item label="Cylinder Cost">
                <el-input v-model="form.plate_details.cylinder_cost" />
              </el-form-item>
              <el-form-item label="Material Model">
                <el-input v-model="form.plate_details.material_model" />
              </el-form-item>
              <el-form-item label="Plate Thickness">
                <el-input v-model="form.plate_details.plate_thickness" />
              </el-form-item>
              <el-form-item label="Bag Type">
                <el-input v-model="form.plate_details.bag_type" />
              </el-form-item>
              <el-form-item label="Set Type">
                <el-input v-model="form.plate_details.set_type" />
              </el-form-item>
              <el-form-item label="Production Time">
                <el-input v-model="form.plate_details.production_time" />
              </el-form-item>
            </div>
            <el-collapse class="returns-collapse">
              <el-collapse-item title="Returns / 返还物" name="returns">
                <div class="field-grid returns-grid">
                  <el-form-item v-for="item in returnItemFields" :key="item.key" :label="item.label">
                    <el-input v-model="form.plate_details[item.key]" inputmode="numeric" @change="syncReturnsSummary" />
                  </el-form-item>
                </div>
              </el-collapse-item>
            </el-collapse>
          </el-tab-pane>

          <el-tab-pane v-if="false && form.plate_details.order_type === 'dechrome'" label="Dechrome" name="dechrome">
            <div class="field-grid">
              <el-form-item label="Date">
                <el-date-picker v-model="form.plate_details.order_date" value-format="YYYY-MM-DD" type="date" />
              </el-form-item>
              <el-form-item label="Plan">
                <el-input v-model="form.plate_details.dechrome_plan" />
              </el-form-item>
              <el-form-item label="DeliveryTime">
                <el-date-picker v-model="form.plate_details.delivery_time" value-format="YYYY-MM-DD" type="date" />
              </el-form-item>
              <el-form-item label="Original NO">
                <el-input v-model="form.plate_details.original_no" />
              </el-form-item>
              <el-form-item label="NO">
                <el-input v-model="form.plate_details.no" />
              </el-form-item>
              <el-form-item label="C">
                <el-input v-model="form.plate_details.c_value" />
              </el-form-item>
              <el-form-item label="L">
                <el-input v-model="form.plate_details.l_value" />
              </el-form-item>
              <el-form-item label="D">
                <el-input v-model="form.plate_details.dia" />
              </el-form-item>
              <el-form-item label="Computer Position">
                <el-input v-model="form.plate_details.computer_position" />
              </el-form-item>
              <el-form-item label="Cylinder Model">
                <el-input v-model="form.plate_details.cylinder_model" />
              </el-form-item>
              <el-form-item label="Charge">
                <el-select v-model="form.plate_details.charge">
                  <el-option label="Chargeable" value="yes" />
                  <el-option label="Free" value="no" />
                </el-select>
              </el-form-item>
              <el-form-item label="总支数">
                <el-input v-model="form.plate_details.total_branch" />
              </el-form-item>
              <el-form-item label="财务备注" class="wide-field">
                <el-input v-model="form.plate_details.finance_note" />
              </el-form-item>
              <el-form-item label="接稿员">
                <el-input v-model="form.plate_details.receiver_name" />
              </el-form-item>
              <el-form-item label="填表员">
                <el-input v-model="form.plate_details.form_filler" />
              </el-form-item>
              <el-form-item label="镀铬要求" class="wide-field">
                <el-input v-model="form.plate_details.chrome_requirement" />
              </el-form-item>
              <el-form-item label="打样要求" class="wide-field">
                <el-input v-model="form.plate_details.polishing_requirement" />
              </el-form-item>
            </div>
          </el-tab-pane>

          <el-tab-pane v-if="false && form.plate_details.order_type === 'rework'" label="Rework" name="rework">
            <div class="field-grid">
              <el-form-item label="返工来源版号">
                <el-input v-model="form.plate_details.rework_source_cylinder_no" />
              </el-form-item>
              <el-form-item label="返工目标工序">
                <el-input v-model="form.plate_details.rework_target_step" placeholder="电雕 / 镀铬 / 打样 / 检验" />
              </el-form-item>
              <el-form-item label="返工数量">
                <el-input v-model="form.plate_details.rework_quantity" />
              </el-form-item>
              <el-form-item label="Charge">
                <el-select v-model="form.plate_details.rework_chargeable">
                  <el-option label="Chargeable" value="yes" />
                  <el-option label="Free" value="no" />
                </el-select>
              </el-form-item>
              <el-form-item label="返工原因" class="wide-field">
                <el-input v-model="form.plate_details.rework_reason" type="textarea" :rows="4" />
              </el-form-item>
              <el-form-item label="检验/处理要求" class="wide-field">
                <el-input v-model="form.plate_details.inspection_requirement" type="textarea" :rows="4" />
              </el-form-item>
            </div>
          </el-tab-pane>

          <el-tab-pane v-if="false" label="颜色明细" name="colors">
            <div class="table-tools">
              <span>颜色 / 数量 / 直径</span>
              <el-button type="primary" :icon="Plus" @click="addColorRow">新增颜色</el-button>
            </div>
            <el-table :data="form.color_rows" row-key="uid" class="dense-table">
              <el-table-column label="Color NO" width="110">
                <template #default="{ row }"><el-input v-model="row.color_no" /></template>
              </el-table-column>
              <el-table-column label="PrintColor" min-width="140">
                <template #default="{ row }"><el-input v-model="row.print_color" /></template>
              </el-table-column>
              <el-table-column label="QTY" width="110">
                <template #default="{ row }"><el-input v-model="row.qty" /></template>
              </el-table-column>
              <el-table-column label="Dia" width="110">
                <template #default="{ row }"><el-input v-model="row.dia" /></template>
              </el-table-column>
              <el-table-column label="Real Dia" width="120">
                <template #default="{ row }"><el-input v-model="row.real_dia" /></template>
              </el-table-column>
              <el-table-column label="Public No." min-width="130">
                <template #default="{ row }"><el-input v-model="row.public_no" /></template>
              </el-table-column>
              <el-table-column label="Remarks" min-width="150">
                <template #default="{ row }"><el-input v-model="row.remarks" /></template>
              </el-table-column>
              <el-table-column label="操作" width="90" fixed="right">
                <template #default="{ $index }">
                  <el-button text type="danger" :disabled="form.color_rows.length === 1" @click="removeColorRow($index)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

        </el-tabs>

        <div class="drawer-actions">
          <el-button @click="drawerVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="createOrder">保存并打开委托书</el-button>
        </div>
      </el-form>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Plus, Refresh, Search } from '@element-plus/icons-vue'
import { apiClient } from '../api/client'
import type { Customer, InventoryLot, PageResponse, PlateNumberReservation, Product, SalesOrder, UserOption } from '../api/types'
import { hasPermission, session } from '../stores/session'
import { customerUserPriority, sortCustomersForCurrentUser } from '../utils/customerPriority'
import { formatCurrency } from '../utils/format'
import { orderStatusMap, statusLabel } from '../utils/status'

interface OrderItemForm {
  uid: string
  product_id: string
  product_name: string
  specification: string
  quantity: number
  unit: string
  unit_price: number
  remark: string
}

interface PlateDetailsForm {
  [key: string]: string
}

type CustomerPriceRule = NonNullable<Customer['price_rules']>[number]

interface ColorRowForm {
  uid: string
  color_no: string
  print_color: string
  qty: string
  dia: string
  real_dia: string
  public_no: string
  printing_method: string
  remarks: string
}

const router = useRouter()
const keyword = ref('')
const statusFilter = ref('')
const orderTypeFilter = ref('')
const orders = ref<SalesOrder[]>([])
const customers = ref<Customer[]>([])
const products = ref<Product[]>([])
const users = ref<UserOption[]>([])
const customerMaterials = ref<InventoryLot[]>([])
const selectedCustomerMaterialLotId = ref('')
const customerMaterialUseQty = ref<number | undefined>(undefined)
const customerPriceRules = ref<CustomerPriceRule[]>([])
const plateNumbers = ref<PlateNumberReservation[]>([])
const drawerVisible = ref(false)
const saving = ref(false)
const requestingPlateNumbers = ref(false)
const previewingPlateNumber = ref(false)
const plateNumberRequestCount = ref(1)
const activeCreateTab = ref('basic')

const form = reactive({
  customer_id: '',
  due_date: '',
  priority: 'normal',
  remark: '',
  plate_details: {} as PlateDetailsForm,
  color_rows: [] as ColorRowForm[],
  items: [] as OrderItemForm[]
})

const orderTotal = computed(() => form.items.reduce((sum, item) => sum + itemAmount(item), 0))
const selectedCustomerMaterial = computed(
  () => customerMaterials.value.find((material) => material.id === selectedCustomerMaterialLotId.value) || null
)
const customerPriceHint = computed(() => {
  const rule = findCustomerPriceRule()
  const price = priceFromCustomerRule(rule)
  return price === null ? '' : `matched unit price: ${formatCurrency(price)}`
})
const canViewHistory = computed(() => hasPermission('order:history:view'))
const historyStatuses = new Set(['paid', 'archived', 'cancelled'])
const platePrefixByKind: Record<string, string> = {
  normal: 'S',
  ppl: 'P',
  special: 'B'
}
const plateNumberKindOptions = [
  { label: 'Normal (S)', value: 'normal' },
  { label: 'PPL (P)', value: 'ppl' },
  { label: 'Special Plate (B)', value: 'special' }
]
const revisionTypeOptions = [
  { label: 'Revision (C)', value: 'revision' },
  { label: 'Remake (R)', value: 'remake' }
]
const reworkTypeOptions = [
  { label: 'Internal Rework (IR)', value: 'internal_rework' },
  { label: 'External Rework (OR)', value: 'external_rework' },
  { label: 'Remake (R)', value: 'remake' }
]
const orderTypeOptions = [
  { label: 'New Cylinder', value: 'new_cylinder' },
  { label: 'Revision / Remake', value: 'old_cylinder' },
  { label: 'Dechrome (Chargeable / Free)', value: 'dechrome' },
  { label: 'Rework (Chargeable / Free)', value: 'rework' }
]
const repeatCountOptions = Array.from({ length: 20 }, (_, index) => String(index + 1))
const cylinderMakingOptions = ['Steel bending', 'Iron pipe']
const printingMethodOptions = ['inside', 'outside', 'outside+inside', 'inside+outside']
const printingMaterialOptions = ['PET', 'OPP', 'PE', 'Paper']
const materialSupplyOptions = [
  { label: 'New', value: 'new' },
  { label: 'Self-bring', value: 'self-bring' },
  { label: 'New + Self-bring', value: 'new+self-bring' }
]
const returnItemFields = [
  { key: 'returns_color_print', label: 'Color Print' },
  { key: 'returns_laser_print', label: 'Laser Print' },
  { key: 'returns_sample', label: 'Sample' },
  { key: 'returns_chromalin_print', label: 'Chromalin Print' },
  { key: 'returns_color_separation', label: 'Color Separation' },
  { key: 'returns_proofing_color_print', label: 'Proofing color Print' }
] as const

const plateKeys = [
  'order_type',
  'customer_text',
  'product_name',
  'total_qty',
  'unit',
  'unit_l',
  'straight',
  'cylinder_id',
  'increase',
  'hole',
  'flange',
  'cylinder_model',
  'cylinder_making',
  'new_material',
  'material',
  'printing_material',
  'new_qty',
  'self_bring_qty',
  'unit_w',
  'crossway',
  'order_date',
  'order_datetime',
  'order_time',
  'dynamic_balance',
  'slope',
  'original_no',
  'printing_method',
  'self_bring',
  'production_time',
  'cylinder_cost',
  'copper_thickness',
  'key_way',
  'returns',
  'archives',
  'inspection_requirement',
  'no',
  'sample_no',
  'printings',
  'salesman',
  'sign_in_person',
  'c_value',
  'l_value',
  'material_model',
  'plate_thickness',
  'cylinder_structure',
  'address',
  'lister',
  'bag_type',
  'material_new',
  'set_type',
  'mark_line',
  'test_line',
  'test_spot',
  'computer_position',
  'production_position',
  'common_remarks',
  'engraving_requirement',
  'proofing_requirement',
  'computer_requirement',
  'color_separation',
  'engraving_note',
  'dechrome_plan',
  'delivery_time',
  'charge',
  'total_branch',
  'finance_note',
  'receiver_name',
  'form_filler',
  'chrome_requirement',
  'polishing_requirement',
  'rework_reason',
  'rework_source_cylinder_no',
  'rework_target_step',
  'rework_quantity',
  'rework_chargeable',
  'reserved_plate_number_id',
  'plate_number_kind',
  'derivation_type',
  'derived_source_cylinder_no',
  'old_cyl_no',
  'dia',
  'width',
  'hor_ver',
  'returns_color_print',
  'returns_laser_print',
  'returns_sample',
  'returns_chromalin_print',
  'returns_color_separation',
  'returns_proofing_color_print'
]

const currentPlatePrefix = computed(() => platePrefixByKind[form.plate_details.plate_number_kind || 'normal'] || 'S')
const availablePlateNumbers = computed(() =>
  plateNumbers.value.filter((item) => item.status === 'reserved' && item.prefix === currentPlatePrefix.value)
)
const selectedReservation = computed(() =>
  plateNumbers.value.find((item) => item.id === form.plate_details.reserved_plate_number_id)
)

function newUid() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function formatLocalDate(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatLocalTime(date: Date) {
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  return `${hours}:${minutes}:${seconds}`
}

function formatLocalDateTime(date: Date) {
  return `${formatLocalDate(date)} ${formatLocalTime(date)}`
}

function stampOrderSubmitTime() {
  const now = new Date()
  form.plate_details.order_datetime = formatLocalDateTime(now)
  form.plate_details.order_date = formatLocalDate(now)
  form.plate_details.order_time = formatLocalTime(now)
}

function todayString() {
  return formatLocalDate(new Date())
}

function datePlusDays(days: number) {
  const date = new Date()
  date.setDate(date.getDate() + days)
  return formatLocalDate(date)
}

function blankPlateDetails(): PlateDetailsForm {
  return Object.fromEntries(plateKeys.map((key) => [key, ''])) as PlateDetailsForm
}

function blankColorRow(): ColorRowForm {
  return {
    uid: newUid(),
    color_no: '',
    print_color: '',
    qty: '',
    dia: '',
    real_dia: '',
    public_no: '',
    printing_method: '',
    remarks: ''
  }
}

function blankItem(): OrderItemForm {
  return {
    uid: newUid(),
    product_id: '',
    product_name: '',
    specification: '',
    quantity: 1,
    unit: '件',
    unit_price: 0,
    remark: ''
  }
}

function resetCustomerMaterialUse(clearPlateFields = false) {
  selectedCustomerMaterialLotId.value = ''
  customerMaterialUseQty.value = undefined
  if (!clearPlateFields) return
  form.plate_details.self_bring_qty = ''
  form.plate_details.self_bring = ''
  if (form.plate_details.new_material === 'self-bring' || form.plate_details.material === 'self-bring') {
    form.plate_details.new_material = 'new'
    form.plate_details.material = 'new'
    syncMaterialFields()
  }
}

function resetForm() {
  const now = new Date()
  Object.assign(form, {
    customer_id: '',
    due_date: datePlusDays(3),
    priority: 'normal',
    remark: '',
      plate_details: {
        ...blankPlateDetails(),
        order_type: 'new_cylinder',
        plate_number_kind: 'normal',
        derivation_type: 'revision',
        order_date: formatLocalDate(now),
        order_datetime: formatLocalDateTime(now),
        order_time: formatLocalTime(now),
        straight: '1',
        crossway: '1',
        cylinder_making: 'Steel bending',
        printing_method: 'inside',
        printing_material: 'PET',
        new_material: 'new',
        material: 'new',
        new_qty: '',
        self_bring_qty: '',
        returns_color_print: '0',
        returns_laser_print: '0',
        returns_sample: '0',
        returns_chromalin_print: '0',
        returns_color_separation: '0',
        returns_proofing_color_print: '0',
        charge: 'yes',
        rework_chargeable: 'yes'
    },
    color_rows: [blankColorRow()],
    items: [blankItem()]
  })
  customerMaterials.value = []
  resetCustomerMaterialUse(true)
  customerPriceRules.value = []
  plateNumberRequestCount.value = 1
  activeCreateTab.value = 'basic'
}

function errorMessage(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || '操作失败'
}

function itemAmount(item: OrderItemForm) {
  return Number(item.quantity || 0) * Number(item.unit_price || 0)
}

function orderTypeLabel(value: unknown) {
  return orderTypeOptions.find((type) => type.value === String(value || 'new_cylinder'))?.label || 'New Cylinder'
}

function applyOrderType() {
  form.plate_details.reserved_plate_number_id = ''
  form.plate_details.original_no = ''
  form.plate_details.derived_source_cylinder_no = ''
  form.plate_details.rework_source_cylinder_no = ''
  clearPrimaryPlateNumber()
  if (form.plate_details.order_type === 'new_cylinder') {
    form.plate_details.plate_number_kind = form.plate_details.plate_number_kind || 'normal'
    form.plate_details.derivation_type = 'revision'
    activeCreateTab.value = 'basic'
  } else if (form.plate_details.order_type === 'old_cylinder') {
    form.plate_details.derivation_type = 'revision'
    activeCreateTab.value = 'basic'
  } else if (form.plate_details.order_type === 'dechrome') {
    activeCreateTab.value = 'dechrome'
    form.priority = 'urgent'
  } else if (form.plate_details.order_type === 'rework') {
    form.plate_details.derivation_type = 'internal_rework'
    activeCreateTab.value = 'rework'
    form.priority = 'urgent'
  }
  applyCustomerPriceToFirstItem(true)
}

function cleanObject<T extends Record<string, string>>(value: T) {
  return Object.fromEntries(Object.entries(value).filter(([, fieldValue]) => String(fieldValue ?? '').trim() !== ''))
}

function cleanColorRows() {
  return form.color_rows
    .map(({ uid: _uid, ...row }) => cleanObject(row))
    .filter((row) => Object.keys(row).length > 0)
}

function parseQuantity(value: string) {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1
}

function parsePlateNumber(value: string | undefined) {
  const normalized = String(value ?? '').replace(/,/g, '').trim()
  if (!normalized) return null
  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? parsed : null
}

function formatPlateNumber(value: number, precision = 2) {
  return value.toFixed(precision).replace(/\.?0+$/, '')
}

function syncCValue() {
  const unitL = parsePlateNumber(form.plate_details.unit_l)
  const straight = parsePlateNumber(form.plate_details.straight)
  if (unitL === null || straight === null) return
  form.plate_details.c_value = formatPlateNumber(unitL * straight, 3)
}

function syncDiaSeries() {
  const baseDia = parsePlateNumber(form.plate_details.dia || form.color_rows[0]?.dia)
  const increase = parsePlateNumber(form.plate_details.increase)
  if (baseDia === null || increase === null) return
  form.color_rows.forEach((row, index) => {
    row.dia = (baseDia + (index * increase) / 100).toFixed(2)
    row.real_dia ||= row.dia
  })
}

function syncColorDefaults() {
  if (!form.color_rows.length) {
    form.color_rows.push(blankColorRow())
  }
  form.color_rows.forEach((row, index) => {
    row.color_no ||= String(index - 1)
    row.printing_method ||= form.plate_details.printing_method || ''
    if (!row.dia && form.plate_details.dia) row.dia = form.plate_details.dia
    if (!row.real_dia && row.dia) row.real_dia = row.dia
  })
  const first = form.color_rows[0]
  if (first) {
    first.qty ||= form.plate_details.total_qty || ''
  }
}

function syncEntrustAliases() {
  const details = form.plate_details
  const unitParts = [details.unit_l, details.unit_w].map((item) => String(item || '').trim()).filter(Boolean)
  if (!details.unit && unitParts.length) {
    details.unit = unitParts.join('*')
  }
  const horVerParts = [details.straight, details.crossway].map((item) => String(item || '').trim()).filter(Boolean)
  if (!details.hor_ver && horVerParts.length) {
    details.hor_ver = horVerParts.join('*')
  }
  details.width ||= details.unit_w || ''
  details.material_new ||= details.new_material || details.material || ''
  details.old_cyl_no ||= details.derived_source_cylinder_no || details.rework_source_cylinder_no || details.original_no || ''
  if (!details.l_value && details.unit_l) details.l_value = details.unit_l
  syncMaterialFields()
  syncReturnsSummary()
}

function syncPlateDimensions() {
  syncCValue()
  syncPlateToFirstItem()
}

function syncMaterialFields() {
  const materialMode = String(form.plate_details.new_material || form.plate_details.material || 'new')
  form.plate_details.material = materialMode
  form.plate_details.material_new = materialMode
  if (materialMode === 'new') {
    form.plate_details.new_qty = form.plate_details.total_qty || form.plate_details.new_qty || ''
    form.plate_details.self_bring_qty = ''
    form.plate_details.self_bring = '0'
  } else if (materialMode === 'self-bring') {
    form.plate_details.self_bring_qty = form.plate_details.self_bring_qty || form.plate_details.total_qty || ''
    form.plate_details.new_qty = ''
    form.plate_details.self_bring = form.plate_details.self_bring_qty || '1'
  } else {
    form.plate_details.self_bring = form.plate_details.self_bring_qty || ''
  }
}

function syncReturnsSummary() {
  const summary = returnItemFields
    .map((item) => {
      const quantity = String(form.plate_details[item.key] || '').trim()
      return quantity && quantity !== '0' ? `${item.label}: ${quantity}` : ''
    })
    .filter(Boolean)
    .join(' / ')
  form.plate_details.returns = summary
}

async function loadOrders() {
  const { data } = await apiClient.get<PageResponse<SalesOrder>>('/sales-orders', {
    params: {
      keyword: keyword.value || undefined,
      status_filter: statusFilter.value || undefined,
      order_type: orderTypeFilter.value || undefined,
      include_history: statusFilter.value ? historyStatuses.has(statusFilter.value) : false
    }
  })
  orders.value = data.items
}

async function fetchAllPages<T>(
  path: string,
  params: Record<string, string | number | boolean | undefined> = {}
) {
  const pageSize = 100
  let page = 1
  const items: T[] = []

  while (true) {
    const { data } = await apiClient.get<PageResponse<T>>(path, {
      params: {
        ...params,
        page,
        page_size: pageSize
      }
    })
    items.push(...data.items)

    if (items.length >= data.total || data.items.length === 0) {
      return items
    }

    page += 1
  }
}

async function loadOptions() {
  const [customerItems, productItems] = await Promise.all([
    fetchAllPages<Customer>('/customers'),
    apiClient.get<Product[]>('/products/options').then((response) => response.data)
  ])
  customers.value = sortCustomersForCurrentUser(customerItems, session.user)
  products.value = productItems
  try {
    const { data } = await apiClient.get<UserOption[]>('/users/options', { params: { role_code: 'sales' } })
    users.value = data
  } catch {
    users.value = []
  }
  if (form.customer_id) {
    void applyCustomer()
  }
}

function userDisplayName(user?: UserOption) {
  return user ? user.real_name || user.username : ''
}

function customerSalesmanName(customer: Customer) {
  const directName = String(customer.salesperson_name || '').trim()
  if (directName) return directName
  const user = users.value.find((item) => item.id === customer.salesperson_id)
  return userDisplayName(user)
}

function positiveNumber(value: unknown) {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

function matchesRuleRange(value: number | null, minValue: unknown, maxValue: unknown) {
  if (value === null) return true
  const min = positiveNumber(minValue)
  const max = positiveNumber(maxValue)
  return (min === null || value > min) && (max === null || value <= max)
}

function currentPlateCm2() {
  const l = parsePlateNumber(form.plate_details.unit_l || form.plate_details.l_value)
  const c = parsePlateNumber(form.plate_details.c_value)
  if (l === null || c === null) return null
  return l * c
}

function findCustomerPriceRule() {
  const l = parsePlateNumber(form.plate_details.unit_l || form.plate_details.l_value)
  const c = parsePlateNumber(form.plate_details.c_value)
  const cm2 = currentPlateCm2()
  return (
    customerPriceRules.value.find(
      (rule) =>
        matchesRuleRange(cm2, rule.min_cm2, rule.max_cm2) &&
        matchesRuleRange(l, rule.min_l, rule.max_l) &&
        matchesRuleRange(c, rule.min_c, rule.max_c)
    ) || null
  )
}

function priceFromCustomerRule(rule: CustomerPriceRule | null) {
  if (!rule) return null
  const orderType = String(form.plate_details.order_type || 'new_cylinder')
  if (orderType === 'old_cylinder') {
    return positiveNumber(rule.old_pcs)
  }
  if (orderType === 'dechrome' || orderType === 'rework') {
    return positiveNumber(rule.repair_chromium_pcs) ?? positiveNumber(rule.old_pcs)
  }
  return positiveNumber(rule.special_cyl_price) ?? positiveNumber(rule.old_pcs) ?? positiveNumber(rule.repair_chromium_pcs)
}

function applyCustomerPriceToFirstItem(force = false) {
  const firstItem = form.items[0]
  if (!firstItem) return false
  const matchedPrice = priceFromCustomerRule(findCustomerPriceRule())
  const fallbackPrice = positiveNumber(form.plate_details.customer_minimum_price)
  const nextPrice = matchedPrice ?? fallbackPrice
  if (nextPrice === null) return false
  if (!force && Number(firstItem.unit_price || 0) > 0) return false
  firstItem.unit_price = nextPrice
  return true
}

function mergeCustomerOption(customer: Customer) {
  const index = customers.value.findIndex((item) => item.id === customer.id)
  const nextCustomers = [...customers.value]
  if (index >= 0) {
    nextCustomers.splice(index, 1, customer)
  } else {
    nextCustomers.push(customer)
  }
  customers.value = sortCustomersForCurrentUser(nextCustomers, session.user)
}

function isCurrentUserCustomer(customer: Customer) {
  return Number.isFinite(customerUserPriority(customer, session.user))
}

async function loadCustomerDetail(customerId: string) {
  try {
    const { data } = await apiClient.get<Customer>(`/customers/${customerId}`)
    mergeCustomerOption(data)
    return data
  } catch {
    return customers.value.find((item) => item.id === customerId) || null
  }
}

function applyCustomerDefaults(customer: Customer) {
  form.plate_details.customer_text = customer.name
  form.plate_details.address = customer.address || ''
  form.plate_details.salesman = customerSalesmanName(customer)
  form.plate_details.customer_minimum_price = customer.minimum_price ? String(customer.minimum_price) : ''
  customerPriceRules.value = customer.price_rules || []
  if (customer.lister) {
    form.plate_details.lister = customer.lister
  }
  applyCustomerPriceToFirstItem()
}

function syncCustomerMaterialQty(value?: number | null) {
  if (!selectedCustomerMaterial.value) return
  const quantity = Number(value ?? customerMaterialUseQty.value ?? 0)
  form.plate_details.self_bring_qty = quantity > 0 ? String(quantity) : ''
  form.plate_details.self_bring = form.plate_details.self_bring_qty || ''
}

function applyCustomerMaterialSelection(lotId?: string) {
  const material = customerMaterials.value.find((item) => item.id === lotId)
  if (!material) {
    resetCustomerMaterialUse(true)
    return
  }
  const available = Number(material.quantity_on_hand || 0)
  const preferredQuantity = Number(form.plate_details.self_bring_qty || form.plate_details.total_qty || 0)
  customerMaterialUseQty.value = Math.min(available, preferredQuantity > 0 ? preferredQuantity : available)
  form.plate_details.new_material = 'self-bring'
  form.plate_details.material = 'self-bring'
  syncCustomerMaterialQty(customerMaterialUseQty.value)
  syncMaterialFields()
  if (!form.plate_details.product_name) {
    form.plate_details.product_name = material.product_name
  }

  const firstItem = form.items[0] || blankItem()
  if (!form.items.length) {
    form.items.push(firstItem)
  }
  if (!firstItem.product_name) {
    firstItem.product_name = material.product_name
  }
  if (!firstItem.specification) {
    firstItem.specification = material.specification || ''
  }
  firstItem.unit = material.unit || firstItem.unit
}

async function loadCustomerMaterials(customerId: string) {
  try {
    const { data } = await apiClient.get<PageResponse<InventoryLot>>('/inventory/customer-materials', {
      params: { customer_id: customerId, page_size: 20 }
    })
    customerMaterials.value = data.items
    if (
      selectedCustomerMaterialLotId.value &&
      !customerMaterials.value.some((item) => item.id === selectedCustomerMaterialLotId.value)
    ) {
      resetCustomerMaterialUse(true)
    }
  } catch {
    customerMaterials.value = []
    resetCustomerMaterialUse(true)
  }
}

async function loadPlateNumbers() {
  try {
    const { data } = await apiClient.get<PlateNumberReservation[]>('/plate-numbers/my', {
      params: { status: 'reserved' }
    })
    plateNumbers.value = data
  } catch {
    plateNumbers.value = []
  }
}

function clearPrimaryPlateNumber() {
  form.plate_details.cylinder_id = ''
  form.plate_details.no = ''
  form.plate_details.sample_no = ''
}

function applyReservedPlateNumber() {
  const reservation = selectedReservation.value
  if (!reservation) {
    clearPrimaryPlateNumber()
    return
  }
  form.plate_details.cylinder_id = reservation.plate_no
  form.plate_details.no = reservation.plate_no
  form.plate_details.sample_no = reservation.plate_no
  form.plate_details.original_no = reservation.plate_no
}

function handlePlateKindChange() {
  form.plate_details.reserved_plate_number_id = ''
  clearPrimaryPlateNumber()
}

async function requestPlateNumbers() {
  requestingPlateNumbers.value = true
  try {
    const { data } = await apiClient.post<PlateNumberReservation[]>('/plate-numbers/reserve', {
      plate_number_kind: form.plate_details.plate_number_kind || 'normal',
      count: plateNumberRequestCount.value
    })
    await loadPlateNumbers()
    if (!form.plate_details.reserved_plate_number_id && data[0]) {
      form.plate_details.reserved_plate_number_id = data[0].id
      applyReservedPlateNumber()
    }
    ElMessage.success(`Plate numbers reserved: ${data.map((item) => item.plate_no).join(', ')}`)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    requestingPlateNumbers.value = false
  }
}

async function returnSelectedPlateNumber() {
  const reservation = selectedReservation.value
  if (!reservation) {
    ElMessage.warning('请选择要退回的版号')
    return
  }
  try {
    await apiClient.post(`/plate-numbers/${reservation.id}/return`)
    ElMessage.success(`Plate number returned: ${reservation.plate_no}`)
    form.plate_details.reserved_plate_number_id = ''
    clearPrimaryPlateNumber()
    await loadPlateNumbers()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function currentDerivedSourcePlateNo() {
  if (form.plate_details.order_type === 'rework') {
    return String(
      form.plate_details.derived_source_cylinder_no ||
        form.plate_details.rework_source_cylinder_no ||
        form.plate_details.original_no ||
        ''
    ).trim()
  }
  return String(
    form.plate_details.derived_source_cylinder_no ||
      form.plate_details.original_no ||
      form.plate_details.cylinder_id ||
      form.plate_details.no ||
      ''
  ).trim()
}

async function loadDerivedPlatePreview() {
  const sourcePlateNo = currentDerivedSourcePlateNo()
  if (!sourcePlateNo) {
    ElMessage.warning('请先填写原版号')
    return false
  }
  previewingPlateNumber.value = true
  try {
    const { data } = await apiClient.get<{ plate_no: string }>('/plate-numbers/derive-preview', {
      params: {
        source_plate_no: sourcePlateNo,
        derivation_type: form.plate_details.derivation_type || 'revision'
      }
    })
    form.plate_details.derived_source_cylinder_no = sourcePlateNo.toUpperCase()
    form.plate_details.original_no = sourcePlateNo.toUpperCase()
    if (form.plate_details.order_type === 'rework') {
      form.plate_details.rework_source_cylinder_no = sourcePlateNo.toUpperCase()
    }
    form.plate_details.cylinder_id = data.plate_no
    form.plate_details.no = data.plate_no
    form.plate_details.sample_no = data.plate_no
    return true
  } catch (error) {
    ElMessage.error(errorMessage(error))
    return false
  } finally {
    previewingPlateNumber.value = false
  }
}

function openCreateDrawer() {
  resetForm()
  drawerVisible.value = true
  loadPlateNumbers()
  if (!customers.value.length || !products.value.length) {
    loadOptions()
  }
}

async function applyCustomer() {
  const customerId = form.customer_id
  if (!customerId) {
    customerMaterials.value = []
    resetCustomerMaterialUse(true)
    customerPriceRules.value = []
    form.plate_details.customer_text = ''
    form.plate_details.address = ''
    form.plate_details.salesman = ''
    return
  }
  resetCustomerMaterialUse(true)
  const cachedCustomer = customers.value.find((item) => item.id === customerId)
  if (cachedCustomer) {
    applyCustomerDefaults(cachedCustomer)
  }
  const customer = await loadCustomerDetail(customerId)
  if (!customer || form.customer_id !== customerId) return
  applyCustomerDefaults(customer)
  loadCustomerMaterials(customer.id)
}

function syncPlateToFirstItem() {
  const firstItem = form.items[0] || blankItem()
  if (!form.items.length) {
    form.items.push(firstItem)
  }
  if (form.plate_details.product_name) {
    firstItem.product_name = form.plate_details.product_name
  }
  if (form.plate_details.total_qty) {
    firstItem.quantity = parseQuantity(form.plate_details.total_qty)
  }
  const specification = [form.plate_details.unit_l && `L ${form.plate_details.unit_l}`, form.plate_details.unit_w && `W ${form.plate_details.unit_w}`]
    .filter(Boolean)
    .join(' / ')
  if (specification) {
    firstItem.specification = specification
  }
  applyCustomerPriceToFirstItem()
}

function applyProductTemplate(row: OrderItemForm) {
  const product = products.value.find((item) => item.id === row.product_id)
  if (!product) return
  row.product_name = product.name
  row.specification = product.specification || ''
  row.unit = product.unit || '件'
  row.unit_price = Number(product.reference_price || 0)
  form.plate_details.product_name = product.name
  if (!form.plate_details.total_qty) {
    form.plate_details.total_qty = String(row.quantity || 1)
  }
}

function addColorRow() {
  form.color_rows.push(blankColorRow())
  syncDiaSeries()
}

function removeColorRow(index: number) {
  form.color_rows.splice(index, 1)
}

function buildValidItems() {
  syncPlateToFirstItem()
  const validItems = form.items.filter((item) => item.product_name && item.quantity > 0)
  if (validItems.length) return validItems
  const productName = form.plate_details.product_name?.trim()
  if (!productName) return []
  return [
    {
      ...blankItem(),
      product_name: productName,
      specification: [form.plate_details.unit_l && `L ${form.plate_details.unit_l}`, form.plate_details.unit_w && `W ${form.plate_details.unit_w}`]
        .filter(Boolean)
        .join(' / '),
      quantity: parseQuantity(form.plate_details.total_qty || '')
    }
  ]
}

async function preparePlateNumberForSubmit() {
  const orderType = form.plate_details.order_type || 'new_cylinder'
  if (orderType === 'new_cylinder') {
    if (!form.plate_details.reserved_plate_number_id) {
      ElMessage.warning('请先申请并选择一个可用版号')
      return false
    }
    applyReservedPlateNumber()
    if (!form.plate_details.cylinder_id) {
      ElMessage.warning('选择的版号不可用，请重新申请')
      return false
    }
  } else if (orderType === 'old_cylinder' || orderType === 'rework') {
    if (!currentDerivedSourcePlateNo()) {
      ElMessage.warning('请先填写原版号')
      return false
    }
    if (!form.plate_details.cylinder_id) {
      const ready = await loadDerivedPlatePreview()
      if (!ready) return false
    }
  }
  return true
}

async function createOrder() {
  const validItems = buildValidItems()
  if (!form.customer_id || !form.due_date || validItems.length === 0) {
    ElMessage.warning('请填写客户、交期，并至少保留一条有效产品明细')
    return
  }
  const materialUseQuantity = Number(customerMaterialUseQty.value || 0)
  if (selectedCustomerMaterialLotId.value && materialUseQuantity <= 0) {
    ElMessage.warning('Please enter customer material use quantity')
    return
  }
  if (selectedCustomerMaterial.value && materialUseQuantity > selectedCustomerMaterial.value.quantity_on_hand) {
    ElMessage.warning('Customer material quantity is not enough')
    return
  }
  const customerMaterialUses =
    selectedCustomerMaterialLotId.value && materialUseQuantity > 0
      ? [
          {
            lot_id: selectedCustomerMaterialLotId.value,
            quantity: materialUseQuantity,
            remark: 'Used by sales order'
          }
        ]
      : []
  const plateNumberReady = await preparePlateNumberForSubmit()
  if (!plateNumberReady) return
  syncCValue()
  syncDiaSeries()
  syncEntrustAliases()
  syncColorDefaults()
  stampOrderSubmitTime()
  saving.value = true
  try {
    const { data } = await apiClient.post<SalesOrder>('/sales-orders', {
      customer_id: form.customer_id,
      due_date: form.due_date,
      route_id: null,
      priority: form.priority,
      remark: form.plate_details.common_remarks || form.remark,
      plate_details: cleanObject(form.plate_details),
      color_rows: cleanColorRows(),
      customer_material_uses: customerMaterialUses,
      items: validItems.map((item) => ({
        product_id: item.product_id || null,
        product_name: item.product_name,
        specification: item.specification || null,
        quantity: item.quantity,
        unit: item.unit || '件',
        unit_price: item.unit_price,
        route_id: null,
        remark: item.remark || null
      }))
    })
    ElMessage.success('委托书草稿已创建')
    drawerVisible.value = false
    statusFilter.value = ''
    await loadPlateNumbers()
    await loadOrders()
    router.push(`/orders/${data.id}/entrust`)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    saving.value = false
  }
}

async function deleteOrder(order: SalesOrder) {
  try {
    await ElMessageBox.confirm(
      `确定删除订单「${order.order_no}」吗？已生成工单的订单需要先处理工单。`,
      '删除订单',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    await apiClient.delete(`/sales-orders/${order.id}`)
    ElMessage.success('订单已删除')
    await loadOrders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(errorMessage(error))
    }
  }
}

async function exportOrders() {
  try {
    const response = await apiClient.get('/sales-orders/export', {
      params: {
        keyword: keyword.value || undefined,
        status_filter: statusFilter.value || undefined,
        order_type: orderTypeFilter.value || undefined,
        include_history: statusFilter.value ? historyStatuses.has(statusFilter.value) : false
      },
      responseType: 'blob'
    })
    const url = URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = `sales-orders-${new Date().toISOString().slice(0, 10)}.xlsx`
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function goDetail(row: SalesOrder) {
  router.push(`/orders/${row.id}`)
}

function goEntrust(row: SalesOrder) {
  router.push(`/orders/${row.id}/entrust`)
}

async function openPrintable(path: string) {
  const popup = window.open('', '_blank')
  try {
    const { data } = await apiClient.get<string>(path, { responseType: 'text' })
    const url = URL.createObjectURL(new Blob([data], { type: 'text/html;charset=utf-8' }))
    if (popup) {
      popup.location.href = url
    } else {
      window.open(url, '_blank')
    }
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (error) {
    popup?.close()
    ElMessage.error(errorMessage(error))
  }
}

function printProductionOrder(row: SalesOrder) {
  openPrintable(`/plate-orders/${row.id}/production-order`)
}

watch([keyword, statusFilter, orderTypeFilter], loadOrders)
watch(() => [form.plate_details.unit_l, form.plate_details.straight], syncCValue)
watch(() => [form.plate_details.dia, form.plate_details.increase, form.color_rows.length], syncDiaSeries)
onMounted(() => {
  resetForm()
  loadOrders()
  loadOptions()
  loadPlateNumbers()
})
</script>

<style scoped>
.order-form {
  display: grid;
  gap: 6px;
}

:global(.order-create-drawer .el-drawer__header) {
  margin-bottom: 8px;
  padding: 14px 18px 8px;
}

:global(.order-create-drawer .el-drawer__body) {
  padding: 8px 18px 14px;
}

.order-form :deep(.el-form-item) {
  margin-bottom: 6px;
}

.order-form :deep(.el-form-item__label) {
  min-height: 18px;
  margin-bottom: 2px;
  padding-bottom: 0;
  font-size: 12px;
  line-height: 1.2;
}

.order-form :deep(.el-input__wrapper),
.order-form :deep(.el-select__wrapper),
.order-form :deep(.el-date-editor.el-input__wrapper),
.order-form :deep(.el-input-number) {
  min-height: 26px;
}

.order-form :deep(.el-input__inner) {
  height: 24px;
  font-size: 12px;
}

.order-tabs {
  --el-border-radius-base: 6px;
}

.order-tabs :deep(.el-tabs__header) {
  margin-bottom: 8px;
}

.order-tabs :deep(.el-tabs__item) {
  height: 30px;
  padding: 0 12px;
  font-size: 13px;
}

.order-form .form-grid {
  grid-template-columns: minmax(190px, 1.3fr) minmax(170px, 1fr) minmax(130px, 0.8fr) minmax(110px, 0.7fr) minmax(150px, 1fr) minmax(150px, 1fr);
  gap: 5px 8px;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(126px, 1fr));
  gap: 5px 8px;
  align-items: start;
}

.quick-order-panel {
  display: grid;
  gap: 6px;
  margin-bottom: 6px;
  padding: 8px;
  border: 1px solid #dbe5ef;
  border-radius: 6px;
  background: #f8fafc;
}

.plate-number-panel {
  display: grid;
  gap: 6px;
  margin-bottom: 6px;
  padding: 8px;
  border: 1px solid #cfdcf0;
  border-radius: 6px;
  background: #f9fbff;
}

.plate-number-grid {
  display: grid;
  grid-template-columns: minmax(136px, 0.8fr) minmax(104px, 0.55fr) minmax(136px, 0.65fr) minmax(220px, 1.3fr) minmax(138px, 0.7fr);
  gap: 5px 8px;
  align-items: start;
}

.derived-plate-grid {
  grid-template-columns: minmax(180px, 1fr) minmax(160px, 0.8fr) minmax(180px, 1fr) minmax(150px, 0.7fr);
}

.plate-number-select {
  min-width: 220px;
}

.quick-order-grid {
  display: grid;
  grid-template-columns: minmax(180px, 1.3fr) repeat(5, minmax(104px, 1fr));
  gap: 5px 8px;
  align-items: start;
}

.full-number {
  width: 100%;
}

.wide-field {
  grid-column: span 2;
}

.table-tools,
.drawer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.table-tools > span {
  color: #667085;
  font-size: 13px;
}

.dense-table :deep(.el-input__wrapper),
.dense-table :deep(.el-select__wrapper) {
  min-height: 26px;
}

.dense-table :deep(.el-input__inner) {
  height: 24px;
  font-size: 12px;
}

.dense-table :deep(.cell) {
  padding-inline: 6px;
}

.order-no-link {
  height: auto;
  padding: 0;
  font-weight: 700;
}

.order-row-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.order-row-actions :deep(.el-button) {
  margin-left: 0;
  padding-inline: 2px;
}

.drawer-actions {
  justify-content: flex-end;
  margin-bottom: 0;
}

.material-alert {
  margin-bottom: 8px;
}

.material-use-grid {
  display: grid;
  grid-template-columns: minmax(220px, 1.5fr) minmax(160px, 0.8fr) minmax(120px, 0.6fr);
  gap: 8px 12px;
  margin-bottom: 8px;
}

.order-search {
  min-width: 260px;
}

.customer-price-alert {
  margin-bottom: 8px;
}

.customer-price-alert :deep(.el-alert__title) {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.customer-price-hint {
  font-weight: 700;
}

.customer-option {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 8px;
  align-items: center;
  width: 100%;
}

.customer-option small {
  color: #667085;
  font-size: 12px;
}

.material-pill {
  display: inline-flex;
  margin-left: 8px;
  font-weight: 700;
}

@media (max-width: 1180px) {
  .field-grid,
  .quick-order-grid,
  .material-use-grid,
  .plate-number-grid,
  .derived-plate-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .field-grid,
  .quick-order-grid,
  .material-use-grid,
  .plate-number-grid,
  .derived-plate-grid {
    grid-template-columns: 1fr;
  }

  .wide-field {
    grid-column: auto;
  }

  .table-tools,
  .drawer-actions {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
