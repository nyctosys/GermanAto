import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { AppShell } from './layout/AppShell'
import { AdminPage } from './pages/AdminPage'
import { AttendancePage } from './pages/AttendancePage'
import { CarDetailPage } from './pages/CarDetailPage'
import { CarsPage } from './pages/CarsPage'
import { CustomerDetailPage } from './pages/CustomerDetailPage'
import { CashReceivedPage } from './pages/CashReceivedPage'
import { DashboardPage } from './pages/DashboardPage'
import { DevicesPage } from './pages/DevicesPage'
import { EmployeesPage } from './pages/EmployeesPage'
import { ExpensesPage } from './pages/ExpensesPage'
import { FinanceHubPage } from './pages/FinanceHubPage'
import { InventoryHistoryPage } from './pages/InventoryHistoryPage'
import { InventoryPage } from './pages/InventoryPage'
import { InvoiceCreatePage } from './pages/InvoiceCreatePage'
import { InvoiceEditPage } from './pages/InvoiceEditPage'
import { InvoiceManagementPage } from './pages/InvoiceManagementPage'
import { LoginPage } from './pages/LoginPage'
import { MonthlyLedgerPage } from './pages/MonthlyLedgerPage'
import { EstimateDetailPage } from './pages/EstimateDetailPage'
import { PendingQuotesPage } from './pages/PendingQuotesPage'
import { QuoteCreatePage } from './pages/QuoteCreatePage'
import { RepairOrderCreatePage } from './pages/RepairOrderCreatePage'
import { RepairOrdersPage } from './pages/RepairOrdersPage'
import { ReportsPage } from './pages/ReportsPage'
import { SalariesPage } from './pages/SalariesPage'
import { SettingsPage } from './pages/SettingsPage'
import { VendorDetailPage } from './pages/VendorDetailPage'
import { VendorsPage } from './pages/VendorsPage'
import { WhatsAppPage } from './pages/WhatsAppPage'
import { WorkerDetailPage } from './pages/WorkerDetailPage'
import { SchedulingPage } from './pages/SchedulingPage'
import { JobCardsPage } from './pages/JobCardsPage'
import { JobCardCreatePage } from './pages/JobCardCreatePage'
import { JobCardDetailPage } from './pages/JobCardDetailPage'
import { LabourCodesPage } from './pages/LabourCodesPage'
import { PublicApprovePage } from './pages/PublicApprovePage'
import { RepairOrderPipelinePage } from './pages/RepairOrderPipelinePage'
import { EntryExitPacketPage } from './pages/EntryExitPacketPage'
import { MoneyInPage } from './pages/MoneyInPage'
import { MoneyOutPage } from './pages/MoneyOutPage'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/approve/:token" element={<PublicApprovePage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<AppShell />}>
              <Route index element={<DashboardPage />} />
              <Route path="cars" element={<CarsPage />} />
              <Route path="cars/:id" element={<CarDetailPage />} />
              <Route path="customers/:id" element={<CustomerDetailPage />} />
              <Route path="inventory" element={<InventoryPage />} />
              <Route path="inventory/history" element={<InventoryHistoryPage />} />
              <Route path="invoices" element={<InvoiceManagementPage />} />
              <Route path="invoices/new" element={<InvoiceCreatePage />} />
              <Route path="invoices/:id/edit" element={<InvoiceEditPage />} />
              <Route path="quotes/new" element={<QuoteCreatePage />} />
              <Route path="quotes/pending" element={<PendingQuotesPage />} />
              <Route path="quotes/:id" element={<EstimateDetailPage />} />
              <Route path="job-cards" element={<JobCardsPage />} />
              <Route path="job-cards/new" element={<JobCardCreatePage />} />
              <Route path="job-cards/:id" element={<JobCardDetailPage />} />
              <Route path="labour-codes" element={<LabourCodesPage />} />
              <Route path="repair-orders" element={<RepairOrdersPage />} />
              <Route path="repair-orders/new" element={<RepairOrderCreatePage />} />
              <Route path="repair-orders/:id/pipeline" element={<RepairOrderPipelinePage />} />
              <Route path="cars/:id/packet" element={<EntryExitPacketPage />} />
              <Route path="money-in" element={<MoneyInPage />} />
              <Route path="money-out" element={<MoneyOutPage />} />
              <Route path="finance" element={<FinanceHubPage />} />
              <Route
                path="finance/daily-expenses"
                element={<ExpensesPage mode="daily" />}
              />
              <Route
                path="finance/major-expenses"
                element={<ExpensesPage mode="major" />}
              />
              <Route path="finance/cash-received" element={<CashReceivedPage />} />
              <Route path="finance/monthly-ledger" element={<MonthlyLedgerPage />} />
              <Route path="vendors" element={<VendorsPage />} />
              <Route path="vendors/:id" element={<VendorDetailPage />} />
              <Route path="hr/employees" element={<EmployeesPage />} />
              <Route path="hr/employees/:id" element={<WorkerDetailPage />} />
              <Route path="hr/scheduling" element={<SchedulingPage />} />
              <Route path="hr/attendance" element={<AttendancePage />} />
              <Route path="hr/salaries" element={<SalariesPage />} />
              <Route path="hr/devices" element={<DevicesPage />} />
              <Route path="reports" element={<ReportsPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="admin" element={<AdminPage />} />
              <Route path="whatsapp" element={<WhatsAppPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
