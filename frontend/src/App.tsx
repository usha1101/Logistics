import { QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { ROUTE_PERMISSIONS } from '@/config/permissions'
import { ROUTES } from '@/config/routes'
import { AppShell } from '@/layouts/AppShell'
import { queryClient } from '@/lib/query-client'
import { AiAgentControlPage } from '@/pages/AiAgentControlPage'
import { CommandCentrePage } from '@/pages/CommandCentrePage'
import { FleetMonitoringPage } from '@/pages/FleetMonitoringPage'
import { LoginPage } from '@/pages/LoginPage'
import { NetworkOverviewPage } from '@/pages/NetworkOverviewPage'
import { OptimizationRecoveryPage } from '@/pages/OptimizationRecoveryPage'
import { OrderManagementPage } from '@/pages/OrderManagementPage'
import { ReportsInsightsPage } from '@/pages/ReportsInsightsPage'
import { SettingsAdminPage } from '@/pages/SettingsAdminPage'
import { SimulationStudioPage } from '@/pages/SimulationStudioPage'
import { WarehouseIntelligencePage } from '@/pages/WarehouseIntelligencePage'
import { WelcomePage } from '@/pages/WelcomePage'
import { AuthProvider } from '@/stores/auth-context'
import type { UserRole } from '@/types/auth'

function AuthenticatedScreen({
  allowedRoles,
  children,
}: {
  allowedRoles: readonly UserRole[]
  children: ReactNode
}) {
  return (
    <ProtectedRoute allowedRoles={allowedRoles}>
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  )
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public Entry & Authentication */}
            <Route path={ROUTES.WELCOME} element={<WelcomePage />} />
            <Route path={ROUTES.LOGIN} element={<LoginPage />} />

            {/* Core Operations */}
            <Route
              path={ROUTES.COMMAND_CENTRE}
              element={
                <AuthenticatedScreen allowedRoles={ROUTE_PERMISSIONS.COMMAND_CENTRE}>
                  <CommandCentrePage />
                </AuthenticatedScreen>
              }
            />
            <Route
              path={ROUTES.NETWORK}
              element={
                <AuthenticatedScreen allowedRoles={ROUTE_PERMISSIONS.NETWORK}>
                  <NetworkOverviewPage />
                </AuthenticatedScreen>
              }
            />
            <Route
              path={ROUTES.FLEET}
              element={
                <AuthenticatedScreen allowedRoles={ROUTE_PERMISSIONS.FLEET}>
                  <FleetMonitoringPage />
                </AuthenticatedScreen>
              }
            />
            <Route
              path={ROUTES.WAREHOUSES}
              element={
                <AuthenticatedScreen allowedRoles={ROUTE_PERMISSIONS.WAREHOUSES}>
                  <WarehouseIntelligencePage />
                </AuthenticatedScreen>
              }
            />

            {/* Execution & Intelligence */}
            <Route
              path={ROUTES.ORDERS}
              element={
                <AuthenticatedScreen allowedRoles={ROUTE_PERMISSIONS.ORDERS}>
                  <OrderManagementPage />
                </AuthenticatedScreen>
              }
            />
            <Route
              path={ROUTES.SIMULATION}
              element={
                <AuthenticatedScreen allowedRoles={ROUTE_PERMISSIONS.SIMULATION}>
                  <SimulationStudioPage />
                </AuthenticatedScreen>
              }
            />
            <Route
              path={ROUTES.AGENTS}
              element={
                <AuthenticatedScreen allowedRoles={ROUTE_PERMISSIONS.AGENTS}>
                  <AiAgentControlPage />
                </AuthenticatedScreen>
              }
            />
            <Route
              path={ROUTES.RECOVERY}
              element={
                <AuthenticatedScreen allowedRoles={ROUTE_PERMISSIONS.RECOVERY}>
                  <OptimizationRecoveryPage />
                </AuthenticatedScreen>
              }
            />

            {/* System & Administration */}
            <Route
              path={ROUTES.REPORTS}
              element={
                <AuthenticatedScreen allowedRoles={ROUTE_PERMISSIONS.REPORTS}>
                  <ReportsInsightsPage />
                </AuthenticatedScreen>
              }
            />
            <Route
              path={ROUTES.SETTINGS}
              element={
                <AuthenticatedScreen allowedRoles={ROUTE_PERMISSIONS.SETTINGS}>
                  <SettingsAdminPage />
                </AuthenticatedScreen>
              }
            />

            {/* Fallback */}
            <Route path="*" element={<Navigate to={ROUTES.WELCOME} replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
export default App
