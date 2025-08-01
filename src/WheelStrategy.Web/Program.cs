using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Configuration;
using WheelStrategy.Core.Configuration;
using WheelStrategy.Core.Interfaces;
using WheelStrategy.Core.Services;
using WheelStrategy.IBKR.Services;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container
builder.Services.AddControllers();
builder.Services.AddSignalR();

// Configure options
builder.Services.Configure<WheelStrategyOptions>(
    builder.Configuration.GetSection(WheelStrategyOptions.SectionName));

// Register services
builder.Services.AddSingleton<IBKRConnectionService>();
builder.Services.AddScoped<IBKRMarketDataService>();
builder.Services.AddScoped<IWheelMonitor, WheelMonitor>();
builder.Services.AddScoped<IWheelScanner, WheelScanner>();
builder.Services.AddScoped<ITradeExecutor, TradeExecutor>();
builder.Services.AddScoped<IAlertManager, AlertManager>();

// Add CORS
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowAll", policy =>
    {
        policy.AllowAnyOrigin()
              .AllowAnyMethod()
              .AllowAnyHeader();
    });
});

var app = builder.Build();

// Configure the HTTP request pipeline
if (app.Environment.IsDevelopment())
{
    app.UseDeveloperExceptionPage();
}

app.UseHttpsRedirection();
app.UseStaticFiles();
app.UseRouting();
app.UseCors("AllowAll");

app.MapControllers();
app.MapHub<DashboardHub>("/dashboardHub");

app.Run(); 