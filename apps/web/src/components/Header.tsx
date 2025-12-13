import { BarChart3 } from 'lucide-react';

export function Header() {
  return (
    <header className="bg-white shadow-sm border-b">
      <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <BarChart3 className="h-8 w-8 text-blue-600" />
            <div>
              <h1 className="text-xl font-bold text-gray-900">AI Trend Analysis</h1>
              <p className="text-sm text-gray-500">실시간 트렌드 분석 대시보드</p>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <span className="text-sm text-gray-500">v0.1.0</span>
          </div>
        </div>
      </div>
    </header>
  );
}
